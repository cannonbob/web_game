from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from db import init_db, db
from models.user import User
from models.game import GameState, SessionCategory, SessionQuestion, Category, Question, QuestionItem, MatchMeGame, PlayerGameState, SessionSetup, AnswerUser
from datetime import timedelta, datetime
from games.game_manager import GameManager
import os
import secrets
import time
from functools import wraps
import logging
import random
from database_manager import db_manager
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Load environment variables from var.env
load_dotenv('var.env')

logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)

# Initialize database
init_db(app)

# Initialize SocketIO with default settings
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize game manager
game_manager = GameManager(socketio)

# Setup utility handlers for movie questions (doesn't set active_game)
game_manager.setup_utility_handlers('movie_guesser')

# Setup utility handlers for ordering game questions (doesn't set active_game)
game_manager.setup_utility_handlers('ordering_game')

# Setup utility handlers for price guesser questions (doesn't set active_game)
game_manager.setup_utility_handlers('price_guesser')

# Note: Sorting game ('tt') handlers are registered when the game starts via game_manager.start_game('tt')
# This is because the handlers need access to the active game instance

# Global variable to track who buzzed for scoring
current_buzzed_player = None
# Multi-item question tracking
current_question_data = None  # Stores the full question data for multi-item questions
current_item_index = 0  # Tracks the current item being displayed
total_items = 0  # Total number of items for the current question

# Silhouette game phase tracking
silhouette_phase = 'idle'  # Tracks current phase: 'idle', 'growing', 'revealing_color', 'complete'

# Session configuration
ACTIVE_SESSION_NAME = "playtest"  # Fallback default session name


def get_active_session():
    """Get the currently active session from database or fallback to ACTIVE_SESSION_NAME"""
    game_state = GameState.query.first()
    if game_state and game_state.active_session_id:
        session = SessionSetup.query.get(game_state.active_session_id)
        if session:
            return session
    # Fallback to ACTIVE_SESSION_NAME or first available session
    session = SessionSetup.query.filter_by(name=ACTIVE_SESSION_NAME).first()
    if not session:
        session = SessionSetup.query.first()
    return session


# Spotify configuration
SPOTIFY_CLIENT_ID = os.getenv('CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('ClIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('REDIRECT_URL')

# Initialize Spotify client with OAuth (deferred initialization)
scope = 'user-read-playback-state,user-modify-playback-state'
auth_manager = None
spotify_client = None
current_spotify_track_id = None  # Track currently loaded Spotify track for resume functionality

def get_spotify_client():
    """Get or create Spotify client with proper error handling"""
    global auth_manager, spotify_client
    
    if auth_manager is None:
        auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=scope,
            cache_path='.spotify_cache',
            show_dialog=False,
            open_browser=False  # Prevent automatic browser opening
        )
    
    if spotify_client is None:
        # Only create client if we have a cached token
        token_info = auth_manager.get_cached_token()
        if token_info:
            spotify_client = spotipy.Spotify(auth_manager=auth_manager)
    
    return spotify_client

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session['username'] != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_game_access(expected_game):
    """
    Validate if the user should have access to a specific game page.
    Returns None if access is valid, otherwise returns a redirect response.

    This ensures users who reconnect are on the correct page.
    """
    game_state = GameState.query.first()

    # If no game state exists, redirect to waiting room
    if not game_state:
        return redirect(url_for('waiting_room'))

    # Check if there's a standalone game active
    if game_state.active_game:
        # If standalone game doesn't match expected game, redirect
        if game_state.active_game != expected_game:
            return redirect(url_for(f'game_{game_state.active_game}'))
        # Standalone game matches - access is valid
        return None

    # Check if platform is active (game board mode)
    if game_state.is_active:
        # In game board mode, check if current_question_data matches this game
        global current_question_data

        if not current_question_data:
            # No active question - redirect to waiting room
            return redirect(url_for('waiting_room'))

        # Determine which game the current question requires
        question_type = current_question_data.get('question_type')

        # Ordering game check
        if current_question_data.get('order_items'):
            if expected_game != 'ordering_game':
                return redirect(url_for('game_ordering_game'))
            return None

        # Price guesser check
        if question_type == 'pg':
            if expected_game != 'price_guesser':
                return redirect(url_for('game_price_guesser'))
            return None

        # Movie guesser check
        if current_question_data.get('input_expected') and current_question_data.get('movie_id'):
            if expected_game != 'movie_guesser':
                return redirect(url_for('game_movie_guesser'))
            return None

        # Top 5 auto-complete check (question_type = 'ac')
        if question_type == 'ac':
            if expected_game != 'top_5':
                return redirect(url_for('game_top_5'))
            return None

        # Multiple choice check
        if question_type == 'mc':
            if expected_game != 'multiple_choice':
                return redirect(url_for('game_multiple_choice'))
            return None

        # Regular input question check
        if current_question_data.get('input_expected'):
            if expected_game != 'question_input':
                return redirect(url_for('game_question_input'))
            return None

        # Buzzer question types
        buzzer_types = ['text', 'image', 'audio', 'video']
        if question_type in buzzer_types:
            if expected_game != 'buzzer':
                return redirect(url_for('game_buzzer'))
            return None

        # Question exists but doesn't match any known type - stay on current page
        return None

    # Platform not active and no standalone game - redirect to waiting room
    return redirect(url_for('waiting_room'))

# Routes
@app.route('/')
def index():
    if 'username' in session:
        if session['username'].lower() == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('waiting_room'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        
        # Check if username exists
        existing_user = User.query.filter_by(username=username).first()
        
        if existing_user:
            session.permanent = True
            session['username'] = username
            if username == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('waiting_room'))
        else:
            # Create new user
            new_user = User(username=username)
            db.session.add(new_user)
            db.session.commit()
            
            session.permanent = True
            session['username'] = username
            
            # Notify all clients that a new user has joined
            socketio.emit('user_joined', {'username': username})
            
            return redirect(url_for('waiting_room'))
    
    return render_template('auth/login.html', error=error)

@app.route('/logout')
def logout():
    username = session.get('username')
    session.pop('username', None)
    socketio.emit('user_left', {'username': username})
    return redirect(url_for('login'))


@app.route('/waiting_room')
@login_required
def waiting_room():
    users = User.query.filter(User.username != 'admin').all()
    game_state = GameState.query.first()
    active_game = game_state.active_game if game_state else None

    # If game is active, redirect to the appropriate game
    if active_game:
        # Map game types to their actual endpoint names for utility games
        game_endpoint_map = {
            'tt': 'game_sorting_game',
            'ordering': 'game_ordering_game',
            'movie_guesser': 'game_movie_guesser',
            'price_guesser': 'game_price_guesser'
        }

        # Use mapped endpoint if it exists, otherwise use default pattern
        endpoint = game_endpoint_map.get(active_game, f'game_{active_game}')
        return redirect(url_for(endpoint))

    return render_template('waiting_room.html', users=users)


@app.route('/admin/setup', methods=['GET'])
@admin_required
def game_setup():
    """Route for setting up categories and questions for the game board."""
    game_state = GameState.query.first()
    
    # Check if there's already an active session with categories and questions
    active_session = SessionSetup.query.first()
    
    # Pass the data to the template
    return render_template('admin/session_setup.html', 
                           game_state=game_state,
                           active_session=active_session)

# Admin panel route
@app.route('/admin')
@admin_required
def admin_panel():
    game_state = GameState.query.first()
    users = User.query.filter(User.username != 'admin').all()
    
    return render_template('admin/admin_panel.html', 
                          users=users, 
                          game_state=game_state,
                          games=game_manager.get_available_games())

# Game display route
@app.route('/display')
def game_display():
    game_state = GameState.query.first()
    users = User.query.filter(User.username != 'admin').all()
    
    print(f"Display route called: game_state={game_state}")
    if game_state:
        print(f"Game state: active={game_state.is_active}, game={game_state.active_game}")
    
    if not game_state:
        print("No game state found, showing waiting screen")
        return render_template('display/waiting.html', users=users)
    
    # If platform is active but no specific game, show game board
    if game_state.is_active and not game_state.active_game:
        print("Platform active but no specific game, showing game board")
        return render_template('display/game_board.html')
    
    # If platform is active with a specific game
    if game_state.is_active and game_state.active_game:
        print(f"Platform active with game {game_state.active_game}, showing game")

        return render_template(f'display/{game_state.active_game}.html')
    
    # Default: show waiting screen
    print("Default case: showing waiting screen")
    return render_template('display/waiting.html', users=users)

# Game routes
@app.route('/game/match_me')
@login_required
def game_match_me():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('match_me')
    if validation_result:
        return validation_result

    return render_template('games/match_me.html')

@app.route('/game/geo_guessr')
@login_required
def game_geo_guessr():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('geo_guessr')
    if validation_result:
        return validation_result

    return render_template('games/geo_guessr.html')

@app.route('/game/flappy_birds')
@login_required
def game_flappy_birds():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('flappy_birds')
    if validation_result:
        return validation_result

    return render_template('games/flappy_birds.html')

@app.route('/game/buzzer')
@login_required
def game_buzzer():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('buzzer')
    if validation_result:
        return validation_result

    return render_template('games/buzzer.html')

@app.route('/game/question_input')
@login_required
def game_question_input():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('question_input')
    if validation_result:
        return validation_result

    return render_template('games/question_input.html')

@app.route('/game/multiple_choice')
@login_required
def game_multiple_choice():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    validation_result = validate_game_access('multiple_choice')
    if validation_result:
        return validation_result

    return render_template('games/multiple_choice.html')

@app.route('/game/coop_puzzle')
@login_required
def game_coop_puzzle():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('coop_puzzle')
    if validation_result:
        return validation_result

    return render_template('games/coop_puzzle.html')

@app.route('/game/movie_guesser')
@login_required
def game_movie_guesser():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('movie_guesser')
    if validation_result:
        return validation_result

    return render_template('games/movie_guesser.html')

@app.route('/game/ordering_game')
@login_required
def game_ordering_game():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('ordering_game')
    if validation_result:
        return validation_result

    return render_template('games/ordering_game.html')

@app.route('/game/sorting_game')
@login_required
def game_sorting_game():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('tt')
    if validation_result:
        return validation_result

    return render_template('games/sorting_game.html')

@app.route('/game/price_guesser')
@login_required
def game_price_guesser():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('price_guesser')
    if validation_result:
        return validation_result

    return render_template('games/price_guesser.html')

@app.route('/game/top_5')
@login_required
def game_top_5():
    if session['username'] == 'admin':
        return redirect(url_for('admin_panel'))

    # Validate game access
    validation_result = validate_game_access('top_5')
    if validation_result:
        return validation_result

    return render_template('games/top_5.html')

# API routes for game data
@app.route('/api/users')
def api_users():
    users = User.query.filter(User.username != 'admin').all()
    return jsonify([user.to_dict() for user in users])

@app.route('/api/game_state')
def api_game_state():
    game_state = GameState.query.first()
    return jsonify(game_state.to_dict() if game_state else {})

@app.route('/api/current_session')
def api_current_session():
    """API endpoint to get current game board session data"""
    try:
        # Get the configured active session
        session = get_active_session()
        if not session:
            return jsonify({'error': 'No session found'}), 404

        session_data = session.to_dict()
        return jsonify(session_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500




def trigger_display_refresh():
    """Utility function to trigger display refresh across all clients."""
    print("Triggering display refresh")
    socketio.emit('display_refresh', {'timestamp': str(datetime.now())}, broadcast=True)

def get_or_create_player_state(user_id, game_type='match_me'):
    """Get or create player game state"""
    player_state = PlayerGameState.query.filter_by(user_id=user_id, game_type=game_type).first()
    if not player_state:
        initial_state = {
            'used_questions': [],
            'used_answers': [],
            'current_question': None,
            'current_answers': [],
            'correct_answer': None,
            'answer_count': 0,
            'correct_count': 0
        }
        player_state = PlayerGameState(user_id=user_id, game_type=game_type)
        player_state.set_game_state(initial_state)
        db.session.add(player_state)
        db.session.commit()
    return player_state

def reset_player_state(user_id, game_type='match_me'):
    """Reset player game state"""
    player_state = PlayerGameState.query.filter_by(user_id=user_id, game_type=game_type).first()
    
    initial_state = {
        'used_questions': [],
        'used_answers': [],
        'current_question': None,
        'current_answers': [],
        'correct_answer': None,
        'answer_count': 0,
        'correct_count': 0
    }
    
    if player_state:
        # Update existing state
        player_state.set_game_state(initial_state)
    else:
        # Create new state
        player_state = PlayerGameState(user_id=user_id, game_type=game_type)
        player_state.set_game_state(initial_state)
        db.session.add(player_state)
    
    db.session.commit()
    return player_state

def get_initial_match_me_state(username):
    """Get initial question for Match Me game"""
    try:
        # Get user
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"User {username} not found")
            return None
            
        # Reset player state for new game
        player_state = reset_player_state(user.id)
        state_data = player_state.to_dict()['game_state']
        
        # Get 5 unique random answers (word_answer)
        print(f"Querying word_combi table for answers...")
        all_answers = db.session.query(MatchMeGame.word_answer).distinct().all()
        print(f"Found {len(all_answers)} distinct answers in database")
        
        answers = db.session.query(MatchMeGame.word_answer).distinct().order_by(db.func.random()).limit(5).all()
        answers = [row[0] for row in answers]
        print(f"Selected answers: {answers}")
        
        if len(answers) < 5:
            print(f"Not enough answers in database for {username} (need 5, got {len(answers)})")
            return None
            
        # Choose one as the correct answer
        correct_answer = random.choice(answers)
        print(f"Selected correct answer: {correct_answer}")
        
        # Get a question (word_question) for this correct answer
        print(f"Looking for questions for answer: {correct_answer}")
        question_result = db.session.query(MatchMeGame.word_question).filter(
            MatchMeGame.word_answer == correct_answer
        ).order_by(db.func.random()).first()
        
        if not question_result:
            print(f"No question found for answer {correct_answer}")
            return None
            
        question = question_result[0]
        print(f"Selected question: {question}")
        
        # Update player state
        state_data['used_questions'].append(question)
        state_data['used_answers'].append(correct_answer)
        state_data['current_question'] = question
        state_data['current_answers'] = answers
        state_data['correct_answer'] = correct_answer
        
        player_state.set_game_state(state_data)
        db.session.commit()
        
        # Create artists array with id and name (using answers as "artists")
        artists = [{'id': i, 'name': answer} for i, answer in enumerate(answers)]
        
        # Find the correct artist ID
        correct_artist_id = next(i for i, artist in enumerate(artists) if artist['name'] == correct_answer)
        
        result = {
            'title_id': 1,  # Not really used in this version
            'title': question,  # The word_question becomes the "title"
            'correct_artist_id': correct_artist_id,
            'artists': artists,  # The word_answers become the "artists"
            'answer_count': state_data['answer_count'],
            'correct_count': state_data['correct_count']
        }
        
        print(f"Returning question data for {username}: {result}")
        return result
        
    except Exception as e:
        print(f"Error in get_initial_match_me_state for {username}: {str(e)}")
        return None

def get_new_match_me_state(username, current_answers, selected_answer, was_correct, correct_answer):
    """Get next question for Match Me game based on previous answer"""
    try:
        # Get user
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"User {username} not found")
            return None
            
        # Get player state
        player_state = get_or_create_player_state(user.id)
        state_data = player_state.to_dict()['game_state']
        
        # Update counts
        state_data['answer_count'] += 1
        if was_correct:
            state_data['correct_count'] += 1
            if selected_answer not in state_data['used_answers']:
                state_data['used_answers'].append(selected_answer)
        
        # Check if game should end
        if state_data['answer_count'] >= 12:
            return {'game_over': True, 'final_score': state_data['correct_count']}
        
        # Determine how many new answers we need
        if not was_correct:
            # Need to replace both selected and correct answers
            new_answers_needed = 2
        else:
            # Only need to replace selected answer
            new_answers_needed = 1
        
        # Get new answers that haven't been used
        used_answers_tuple = tuple(state_data['used_answers']) if state_data['used_answers'] else ('',)
        current_answers_tuple = tuple(current_answers) if current_answers else ('',)
        used_questions_tuple = tuple(state_data['used_questions']) if state_data['used_questions'] else ('',)
        
        # Get new answers that have available questions
        new_answers_query = db.session.query(MatchMeGame.word_answer).distinct().filter(
            ~MatchMeGame.word_answer.in_(used_answers_tuple),
            ~MatchMeGame.word_answer.in_(current_answers_tuple)
        ).filter(
            MatchMeGame.word_answer.in_(
                db.session.query(MatchMeGame.word_answer).filter(
                    ~MatchMeGame.word_question.in_(used_questions_tuple)
                )
            )
        ).order_by(db.func.random()).limit(new_answers_needed)
        
        new_answers_result = new_answers_query.all()
        
        if len(new_answers_result) < new_answers_needed:
            return {'game_over': True, 'final_score': state_data['correct_count']}
        
        new_answers = [row[0] for row in new_answers_result]
        
        # Update answers list
        updated_answers = current_answers.copy()
        
        if not was_correct:
            # Replace both selected and correct answers
            if selected_answer in updated_answers:
                selected_index = updated_answers.index(selected_answer)
                updated_answers[selected_index] = new_answers[0]
            if correct_answer in updated_answers:
                correct_index = updated_answers.index(correct_answer)
                if correct_index != updated_answers.index(new_answers[0]):  # Avoid replacing same position twice
                    updated_answers[correct_index] = new_answers[1] if len(new_answers) > 1 else new_answers[0]
        else:
            # Replace only selected answer
            if selected_answer in updated_answers:
                selected_index = updated_answers.index(selected_answer)
                updated_answers[selected_index] = new_answers[0]
        
        # Ensure all answers are unique
        if len(set(updated_answers)) != len(updated_answers):
            return {'game_over': True, 'final_score': state_data['correct_count']}
        
        # Choose new correct answer from updated list
        new_correct_answer = random.choice(updated_answers)
        
        # Get new question for the correct answer that hasn't been used
        question_query = db.session.query(MatchMeGame.word_question).filter(
            MatchMeGame.word_answer == new_correct_answer,
            ~MatchMeGame.word_question.in_(used_questions_tuple)
        ).order_by(db.func.random()).first()
        
        if not question_query:
            return {'game_over': True, 'final_score': state_data['correct_count']}
        
        new_question = question_query[0]
        
        # Update player state
        state_data['used_questions'].append(new_question)
        state_data['current_question'] = new_question
        state_data['current_answers'] = updated_answers
        state_data['correct_answer'] = new_correct_answer
        
        player_state.set_game_state(state_data)
        db.session.commit()
        
        # Create artists array with id and name
        artists = [{'id': i, 'name': answer} for i, answer in enumerate(updated_answers)]
        
        # Find the correct artist ID
        correct_artist_id = next(i for i, artist in enumerate(artists) if artist['name'] == new_correct_answer)
        
        return {
            'title_id': state_data['answer_count'] + 1,
            'title': new_question,
            'correct_artist_id': correct_artist_id,
            'artists': artists,
            'answer_count': state_data['answer_count'],
            'correct_count': state_data['correct_count']
        }
        
    except Exception as e:
        print(f"Error in get_new_match_me_state for {username}: {str(e)}")
        return None

@app.route('/api/start_platform', methods=['POST'])
@admin_required
def api_start_platform():
    print("\n\n====== START PLATFORM DIRECT API CALLED ======")
    
    try:
        # Clear all players first (except admin)
        print("Clearing all players...")
        users_to_delete = User.query.filter(User.username != 'admin').all()
        
        # First, delete all PlayerGameState records for these users
        for user in users_to_delete:
            print(f"Deleting game states for user: {user.username}")
            PlayerGameState.query.filter_by(user_id=user.id).delete()

        # Delete all AnswerUser records for these users
        from models.game import AnswerUser, PriceGuessUser
        for user in users_to_delete:
            print(f"Deleting answer submissions for user: {user.username}")
            AnswerUser.query.filter_by(user_id=user.id).delete()

        # Delete all PriceGuessUser records for these users
        for user in users_to_delete:
            print(f"Deleting price guess submissions for user: {user.username}")
            PriceGuessUser.query.filter_by(user_id=user.id).delete()

        # Then delete the users themselves
        for user in users_to_delete:
            print(f"Deleting user: {user.username}")
            db.session.delete(user)

        # Reset all session questions 'used' status (use no_autoflush to prevent premature flush)
        print("Resetting session questions 'used' status...")
        with db.session.no_autoflush:
            session_questions_updated = SessionQuestion.query.filter_by(used=True).update({'used': False})
        print(f"Reset {session_questions_updated} session questions")

        # Clear game_data to reset ordering game submissions and other game state
        print("Clearing game_data...")
        game_state = GameState.query.first()
        if game_state:
            game_state.game_data = '{}'
            print("Game data cleared")

        db.session.commit()
        print(f"Cleared {len(users_to_delete)} players from the database")

        # Use the database manager to set the platform active
        success = db_manager.set_platform_active(active=True, game=None)
        
        if success:
            # Emit socket event to notify clients
            print("Broadcasting platform_started event")
            socketio.emit('platform_started', {'timestamp': str(datetime.now())}, broadcast=True)
            
            # Also emit the admin_refresh_display event specifically for the display page
            #socketio.emit('admin_refresh_display', {}, broadcast=True)
            trigger_display_refresh()
            
            print("====== START PLATFORM DIRECT API COMPLETED ======\n")
            return jsonify({"success": True, "players_cleared": len(users_to_delete), "questions_reset": session_questions_updated})
        else:
            print("Database update failed")
            print("====== START PLATFORM DIRECT API FAILED ======\n")
            return jsonify({"success": False, "error": "Database update failed"}), 500
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("====== START PLATFORM DIRECT API FAILED ======\n")
        return jsonify({"success": False, "error": str(e)}), 500
    

@app.route('/api/stop_platform', methods=['POST'])
@admin_required
def api_stop_platform():
    print("\n\n====== STOP PLATFORM DIRECT API CALLED ======")

    try:
        # Clear current question data (same as socket handler does)
        global current_question_data, current_item_index, total_items
        current_question_data = None
        current_item_index = 0
        total_items = 0
        print("Cleared current question data")

        # Use the database manager to set the platform inactive
        success = db_manager.set_platform_active(active=False, game=None)

        if success:
            # End any active game
            if game_manager.get_active_game():
                game_manager.end_game()
                print("Active game ended")

            # Emit socket event to notify clients
            print("Broadcasting platform_stopped event")
            trigger_display_refresh()

            # Redirect all players to waiting room
            socketio.emit('admin_players_goto_waiting_room', {}, broadcast=True)
            print("Sent admin_players_goto_waiting_room to redirect players")

            # Also emit the admin_refresh_display event specifically for the display page
            socketio.emit('admin_refresh_display', {}, broadcast=True)

            print("====== STOP PLATFORM DIRECT API COMPLETED ======\n")
            return jsonify({"success": True})
        else:
            print("Database update failed")
            print("====== STOP PLATFORM DIRECT API FAILED ======\n")
            return jsonify({"success": False, "error": "Database update failed"}), 500
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("====== STOP PLATFORM DIRECT API FAILED ======\n")
        return jsonify({"success": False, "error": str(e)}), 500
    

@app.route('/api/platform_state')
def api_platform_state():
    """API endpoint to check the current platform state using direct database access"""
    try:
        state = db_manager.get_platform_state()
        return jsonify(state)
    except Exception as e:
        print(f"Error getting platform state: {e}")
        return jsonify({"error": str(e)}), 500


# Session Management API endpoints
@app.route('/api/admin/sessions')
@admin_required
def api_get_sessions():
    """Get all available game sessions"""
    try:
        sessions = SessionSetup.query.all()
        game_state = GameState.query.first()
        active_session_id = game_state.active_session_id if game_state else None

        return jsonify({
            'success': True,
            'sessions': [{'id': s.id, 'name': s.name, 'created_at': str(s.created_at)} for s in sessions],
            'active_session_id': active_session_id,
            'platform_active': game_state.is_active if game_state else False
        })
    except Exception as e:
        print(f"Error getting sessions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/select-session', methods=['POST'])
@admin_required
def api_select_session():
    """Select a session to use (only when platform is stopped)"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400

        # Validate session exists
        session_setup = SessionSetup.query.get(session_id)
        if not session_setup:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Check if platform is active
        game_state = GameState.query.first()
        if game_state and game_state.is_active:
            return jsonify({'success': False, 'error': 'Cannot change session while platform is active'}), 400

        # Update active session
        if not game_state:
            game_state = GameState(id=1, is_active=False, active_session_id=session_id)
            db.session.add(game_state)
        else:
            game_state.active_session_id = session_id

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Session "{session_setup.name}" selected',
            'session': {'id': session_setup.id, 'name': session_setup.name}
        })
    except Exception as e:
        print(f"Error selecting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/active-session')
@admin_required
def api_get_active_session():
    """Get the currently active session"""
    try:
        game_state = GameState.query.first()
        if not game_state or not game_state.active_session_id:
            # Fall back to first session or the one matching ACTIVE_SESSION_NAME
            session = SessionSetup.query.filter_by(name=ACTIVE_SESSION_NAME).first()
            if not session:
                session = SessionSetup.query.first()
            return jsonify({
                'success': True,
                'session': {'id': session.id, 'name': session.name} if session else None,
                'platform_active': game_state.is_active if game_state else False
            })

        session = SessionSetup.query.get(game_state.active_session_id)
        return jsonify({
            'success': True,
            'session': {'id': session.id, 'name': session.name} if session else None,
            'platform_active': game_state.is_active
        })
    except Exception as e:
        print(f"Error getting active session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Spotify API endpoints
@app.route('/api/spotify/auth_url')
def get_spotify_auth_url():
    """Get Spotify authorization URL"""
    try:
        # Initialize auth manager if needed
        global auth_manager
        if auth_manager is None:
            auth_manager = SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope=scope,
                cache_path='.spotify_cache',
                show_dialog=False,
                open_browser=False
            )
        
        auth_url = auth_manager.get_authorize_url()
        return jsonify({'auth_url': auth_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/status')
def get_spotify_status():
    """Check if Spotify is authenticated and ready"""
    try:
        client = get_spotify_client()
        if client:
            # Test if we can access the API
            try:
                devices = client.devices()
                return jsonify({
                    'authenticated': True,
                    'devices_available': len(devices['devices']) > 0,
                    'active_device': any(d['is_active'] for d in devices['devices'])
                })
            except Exception as api_error:
                return jsonify({
                    'authenticated': True,
                    'error': 'API access failed',
                    'details': str(api_error)
                })
        else:
            return jsonify({'authenticated': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/complete_auth', methods=['POST'])
def complete_spotify_auth():
    """Complete Spotify authentication with authorization code"""
    global spotify_client, auth_manager
    try:
        data = request.get_json()
        code = data.get('code')
        
        if not code:
            return jsonify({'success': False, 'error': 'No authorization code provided'})
        
        # Make sure auth_manager is initialized
        if auth_manager is None:
            auth_manager = SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope=scope,
                cache_path='.spotify_cache',
                show_dialog=False,
                open_browser=False
            )
        
        # Exchange code for token
        token_info = auth_manager.get_access_token(code)
        if token_info:
            # Reset client to use new token
            spotify_client = None
            print("Spotify authentication completed successfully!")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to get access token'})
            
    except Exception as e:
        print(f"Error completing Spotify auth: {e}")
        return jsonify({'success': False, 'error': str(e)})
    


@socketio.on('start_platform')
def handle_start_platform():
    if 'username' in session and session['username'] == 'admin':
        print("Admin started the platform")

        # Clear global question data to ensure clean state
        global current_question_data, current_item_index, total_items
        current_question_data = None
        current_item_index = 0
        total_items = 0
        print("Cleared global question data when starting platform")

        try:
            # Get game state in a new transaction to ensure fresh data
            with app.app_context():
                game_state = GameState.query.first()

                if game_state:
                    # Update game state
                    game_state.is_active = True
                    game_state.active_game = None
                    game_state.game_data = '{}'  # Clear ordering game submissions and other game state

                    # Explicitly commit the changes
                    db.session.commit()
                    db.session.flush()

                    # Verify the update worked
                    db.session.refresh(game_state)
                    print(f"Game state updated successfully: active={game_state.is_active}, game={game_state.active_game}")
                else:
                    print("No game state found, creating new one")
                    # Create a new game state if none exists
                    game_state = GameState(is_active=True, active_game=None, game_data='{}')
                    db.session.add(game_state)
                    db.session.commit()
                    print("New game state created")

            # End any active game in game_manager
            if game_manager.active_game:
                print(f"Ending active game: {game_manager.active_game}")
                game_manager.end_game()

            # Notify all clients
            trigger_display_refresh()
            print("platform_started event broadcasted")

            # Emit game_ended to update admin panel UI
            emit('game_ended', {}, broadcast=True)
            print("game_ended event emitted to reset admin panel")

        except Exception as e:
            print(f"Error updating game state: {e}")
            import traceback
            traceback.print_exc()

@socketio.on('stop_platform')
def handle_stop_platform():
    if 'username' in session and session['username'] == 'admin':
        # Clear current question data
        global current_question_data, current_item_index, total_items
        current_question_data = None
        current_item_index = 0
        total_items = 0
        print("Cleared current question data when stopping platform")

        # Update the game state to mark platform as inactive
        game_state = GameState.query.first()
        if game_state:
            game_state.is_active = False
            game_state.active_game = None
            db.session.commit()

        # End any active game
        if game_manager.get_active_game():
            game_manager.end_game()

        # Notify all clients
        trigger_display_refresh()

        # Redirect all players to waiting room
        emit('admin_players_goto_waiting_room', {}, broadcast=True)


# SocketIO events
@socketio.on('connect')
def handle_connect(auth=None):
    print(f"Socket.IO: Client connected! Session ID: {request.sid}")
    if 'username' in session:
        username = session['username']
        print(f"Socket.IO: User {username} connected")
        print(f"Socket.IO: Joining user {username} to room '{username}'")
        join_room(username)
        print(f"Socket.IO: User {username} successfully joined room")
        emit('user_joined', {'username': username}, broadcast=True)

        # RECONNECTION LOGIC: Restore game state for reconnecting users
        # Skip admin users - they don't need game state restoration
        if username != 'admin':
            game_state = GameState.query.first()

            if game_state and game_state.is_active:
                print(f"Socket.IO: Restoring game state for reconnecting user {username}")

                # Case 1: Standalone game is active
                if game_state.active_game:
                    print(f"Socket.IO: Standalone game '{game_state.active_game}' is active - forwarding {username}")
                    # Emit game_started event to forward user to the game page
                    emit('game_started', {'game': game_state.active_game})
                    print(f"Socket.IO: Sent game_started event for {game_state.active_game} to {username}")

                    # Check if game has internal state that needs restoration
                    if game_state.active_game == 'geo_guessr' and game_manager.active_game:
                        # Get geo_guessr game state
                        geo_state = game_manager.active_game.get_game_state()
                        print(f"Socket.IO: GeoGuessr state: {geo_state}")

                        # If a round is active, re-emit round_started to restore client state
                        if geo_state.get('status') == 'active' and geo_state.get('current_round', 0) > 0:
                            current_round = geo_state['current_round']
                            total_rounds = geo_state.get('total_rounds', 3)
                            print(f"Socket.IO: Re-emitting geo_guessr_round_started for round {current_round}")
                            emit('geo_guessr_round_started', {
                                'round': current_round,
                                'total_rounds': total_rounds
                            })

                        # If game is ready but no round started, emit ready event
                        elif geo_state.get('status') == 'ready':
                            total_rounds = geo_state.get('total_rounds', 3)
                            emit('geo_guessr_ready', {
                                'total_rounds': total_rounds
                            })

                    # Check flappy_birds state for reconnection
                    elif game_state.active_game == 'flappy_birds' and game_manager.active_game:
                        # Get flappy_birds game state
                        flappy_state = game_manager.active_game.get_game_state()
                        print(f"Socket.IO: Flappy Birds state: {flappy_state}")

                        # If game is active, re-emit started event to enable gameplay
                        if flappy_state.get('status') == 'active':
                            print(f"Socket.IO: Re-emitting flappy_birds_started")
                            emit('flappy_birds_started', {})

                            # Send player's current high score if they have one
                            player_scores = flappy_state.get('player_scores', {})
                            if username in player_scores:
                                player_high_score = player_scores[username]
                                print(f"Socket.IO: Restoring high score for {username}: {player_high_score}")
                                emit('flappy_birds_restore_score', {
                                    'high_score': player_high_score
                                })

                        # If game is ready but not started, emit ready event
                        elif flappy_state.get('status') == 'ready':
                            emit('flappy_birds_ready', {})

                    # Check match_me state for reconnection
                    elif game_state.active_game == 'match_me' and game_manager.active_game:
                        # Get match_me game state
                        match_state = game_manager.active_game.get_game_state()
                        print(f"Socket.IO: Match Me state: {match_state}")

                        # If game is active, re-emit countdown to enable gameplay
                        # Player will start fresh (no progress restoration)
                        if match_state.get('status') == 'active':
                            print(f"Socket.IO: Re-emitting match_me_countdown for reconnection")
                            # Emit countdown with 0 to skip animation and start immediately
                            emit('match_me_reconnect', {})

                        # If game is ready but not started, emit ready event
                        elif match_state.get('status') == 'ready':
                            question_text = current_question_data.get('question_text') if current_question_data else "Match Me"
                            emit('match_me_ready', {'question': question_text})

                # Case 2: Game board is active with a current question
                elif current_question_data:
                    print(f"Socket.IO: Game board active with question - restoring question for {username}")

                    # Re-emit the question_selected event to this user only
                    emit('question_selected', {
                        'question': current_question_data.get('question_text'),
                        'questionData': current_question_data,
                        'currentItemIndex': current_item_index,
                        'totalItems': total_items
                    })

                    # Determine question type and emit appropriate forward event
                    question_type = current_question_data.get('question_type')

                    # Ordering game
                    if current_question_data.get('order_items'):
                        emit('forward_to_ordering_game', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data,
                            'currentItemIndex': current_item_index,
                            'totalItems': total_items
                        })
                        print(f"Socket.IO: Forwarded {username} to ordering game")

                    # Price guesser
                    elif question_type == 'pg':
                        emit('forward_to_price_guesser', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data
                        })
                        print(f"Socket.IO: Forwarded {username} to price guesser")

                    # Movie guesser
                    elif current_question_data.get('input_expected') and current_question_data.get('movie_id'):
                        emit('forward_to_movie_guesser', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data,
                            'currentItemIndex': current_item_index,
                            'totalItems': total_items
                        })
                        print(f"Socket.IO: Forwarded {username} to movie guesser")

                    # Top 5 auto-complete question (question_type = 'ac')
                    elif question_type == 'ac':
                        # Get player's previous guesses if they exist
                        user = User.query.filter_by(username=username).first()
                        previous_guesses = []
                        if user:
                            question_id = current_question_data.get('id')
                            existing_answers = AnswerUser.query.filter_by(
                                user_id=user.id,
                                question_id=question_id
                            ).order_by(AnswerUser.round).all()

                            previous_guesses = [ans.answer_raw for ans in existing_answers]
                            print(f"Socket.IO: Found {len(previous_guesses)} previous guesses for {username}")

                        emit('forward_to_top_5', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data,
                            'previousGuesses': previous_guesses
                        })
                        print(f"Socket.IO: Forwarded {username} to Top 5 with {len(previous_guesses)} previous guesses")

                    # Multiple choice question
                    elif question_type == 'mc':
                        emit('forward_to_mc', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data
                        })
                        print(f"Socket.IO: Forwarded {username} to multiple choice")

                    # Regular input question
                    elif current_question_data.get('input_expected'):
                        emit('forward_to_input', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data
                        })
                        print(f"Socket.IO: Forwarded {username} to question input")

                    # Buzzer question types
                    elif question_type in ['text', 'image', 'audio', 'video', 'silhouette', 'fg']:
                        emit('forward_to_buzzer', {
                            'question': current_question_data.get('question_text'),
                            'questionData': current_question_data
                        })
                        print(f"Socket.IO: Forwarded {username} to buzzer")

                    else:
                        print(f"Socket.IO: Question type '{question_type}' doesn't require forwarding")

                else:
                    print(f"Socket.IO: Game board active but no current question for {username}")

            else:
                print(f"Socket.IO: No active game state for {username}")

    else:
        print("Socket.IO: Client connected but no username in session")

        # Handle display connection (unauthenticated)
        game_state = GameState.query.first()
        if game_state and game_state.is_active:
            # Match Me: Send ready state to display
            if game_state.active_game == 'match_me' and game_manager.active_game:
                match_state = game_manager.active_game.get_game_state()
                if match_state.get('status') == 'ready':
                    question_text = current_question_data.get('question_text') if current_question_data else "Match Me"
                    emit('match_me_ready', {'question': question_text})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Socket.IO: Client disconnected! Session ID: {request.sid}")
    if 'username' in session:
        username = session['username']
        print(f"Socket.IO: User {username} disconnected")
        leave_room(username)
        emit('user_left', {'username': username}, broadcast=True)


@socketio.on('test_socket')
def handle_test_socket(data):
    print(f"Socket.IO: Test event received from {session.get('username', 'unknown')}! Data: {data}")
    emit('test_response', {'message': f'Socket.IO is working! Server received: {data}'})

@socketio.on('select_game')
def handle_select_game(data):
    if 'username' in session and session['username'] == 'admin':
        game_name = data['game']
        
        # Log the action
        print(f"Admin selecting game: {game_name}")
        
        # Initialize the game manager but don't start the actual game yet
        print(f"Calling game_manager.start_game('{game_name}') for initialization")
        success = game_manager.start_game(game_name)
        print(f"Game manager returned: {success}")
        
        if success:
            print("Game manager initialized successfully - players will be forwarded")
            # Emit the game_selected event (this will forward players and display)
            emit('game_started', {'game': game_name}, broadcast=True)

            print(f"Game {game_name} selected successfully - players forwarded")
        else:
            print(f"FAILED to select game {game_name} - game manager returned False")

@socketio.on('start_actual_game')
def handle_start_actual_game(data):
    if 'username' in session and session['username'] == 'admin':
        game_name = data['game']
        
        print(f"Admin starting actual game: {game_name}")
        
        # Get the active game from game manager and start it
        active_game = game_manager.get_active_game()
        if active_game and hasattr(active_game, 'start_game'):
            print("Calling active_game.start_game() for countdown/questions")
            active_game.start_game()
            print("Actual game started successfully")
        else:
            print("No active game found or game doesn't have start_game method")

@socketio.on('end_game')
def handle_end_game():
    if 'username' in session and session['username'] == 'admin':
        print("Admin ending the current game")

        # Clear current question data to prevent reconnection issues
        global current_question_data, current_item_index, total_items
        current_question_data = None
        current_item_index = 0
        total_items = 0
        print("Cleared current question data")

        # End the game using the game manager
        success = game_manager.end_game()

        if success:
            # Emit the game_ended event to update admin panel
            emit('game_ended', {}, broadcast=True)

            # Force display refresh to return to game board/waiting room
            trigger_display_refresh()

            # Redirect all players to waiting room
            emit('admin_players_goto_waiting_room', {}, broadcast=True)

            print("Game ended successfully")
        else:
            print("Failed to end game")

@socketio.on('select_question')
def handle_select_question(data):
    """Handle question selection for game board"""
    global silhouette_phase
    try:
        # Reset silhouette phase for new question
        silhouette_phase = 'idle'

        category_position = int(data['category'])
        question_value = int(data['value'])

        # Get the configured active session
        session_setup = get_active_session()
        if not session_setup:
            emit('error', {'message': 'No session found'})
            return
        
        # Find the category at this position
        session_category = SessionCategory.query.filter_by(
            session_id=session_setup.id,
            position=category_position
        ).first()
        
        if not session_category:
            emit('error', {'message': 'Category not found'})
            return
        
        # Find the question at this position (value / 100 = position)
        question_position = question_value // 100
        session_question = SessionQuestion.query.filter_by(
            session_category_id=session_category.id,
            position=question_position
        ).first()
        
        if not session_question:
            emit('error', {'message': 'Question not found'})
            return
        
        # Delete old player answers for this question (from previous sessions)
        from models.game import AnswerUser
        deleted_count = AnswerUser.query.filter_by(question_id=session_question.question.id).delete()
        print(f"DEBUG: Deleted {deleted_count} old answers for question ID {session_question.question.id}")

        # Mark question as used
        session_question.used = True
        db.session.commit()
        print(f"DEBUG: Committed deletion of old answers for question ID {session_question.question.id}")

        # Initialize multi-item tracking
        global current_question_data, current_item_index, total_items
        question_dict = session_question.question.to_dict()
        current_question_data = question_dict

        print(f"DEBUG: Question selected - multi_item value: {question_dict.get('multi_item')}")
        print(f"DEBUG: Question type: {question_dict.get('question_type')}")
        print(f"DEBUG: Media URL: {question_dict.get('media_url')}")

        # Determine total items for this question
        # multi_item: 0 = cumulative display (add items), 1 = replacement display (replace items)
        # Both modes use item_order grouping and navigation controls
        items = question_dict.get('items', [])
        if items:
            # Get unique item_order values to determine total items
            unique_orders = set(item['item_order'] for item in items)
            total_items = len(unique_orders)

            # Group items by item_order for easier access
            items_by_order = {}
            for item in items:
                order = item['item_order']
                if order not in items_by_order:
                    items_by_order[order] = []
                items_by_order[order].append(item)

            question_dict['items_by_order'] = items_by_order
            question_dict['order_sequence'] = sorted(unique_orders)
            current_item_index = 0  # Start at first item_order group
        else:
            total_items = 1
            current_item_index = 0

        # Emit to all clients
        print(f"DEBUG: Emitting question_selected with:")
        print(f"  - multi_item: {question_dict.get('multi_item')}")
        print(f"  - currentItemIndex: {current_item_index}")
        print(f"  - totalItems: {total_items}")
        print(f"  - items count: {len(items)}")
        print(f"  - unique item_orders: {total_items}")

        # Get answer from answers_expected table (use primary answer or fallback to question.answer)
        answer_to_display = session_question.question.answer  # Fallback
        if session_question.question.expected_answers:
            # Get primary answer or first answer
            primary_answer = next((ans for ans in session_question.question.expected_answers if ans.is_primary), None)
            if primary_answer:
                answer_to_display = primary_answer.answer_raw
            elif session_question.question.expected_answers:
                answer_to_display = session_question.question.expected_answers[0].answer_raw

        # Note: 'question_selected' event is now emitted only for questions that stay on the game board
        # Special game types (match_me, geo_guessr, etc.) handle their own display logic

        # Check if this is an ordering game question
        if session_question.question.order_items and len(session_question.question.order_items) > 0:
            emit('question_selected', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'answer': answer_to_display,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }, broadcast=True)

            emit('forward_to_ordering_game', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }, broadcast=True)

            print(f"Question selected: Category {category_position}, Value {question_value} (Ordering Game)")
            print("Players forwarded to ordering game interface")
        # Check if this is a geo guesser question
        elif session_question.question.question_type == 'gg':
            # Get the location data for this question
            from models.game import GeoGuessrLocation
            location = GeoGuessrLocation.query.filter_by(question_id=session_question.question.id).first()

            if not location:
                emit('error', {'message': 'No location found for this geo_guessr question'})
                return

            # Update game state in database
            print("Updating game state in database for geo_guessr...")
            game_state = GameState.query.first()
            if not game_state:
                game_state = GameState(is_active=True, active_game='geo_guessr')
                db.session.add(game_state)
            else:
                game_state.is_active = True
                game_state.active_game = 'geo_guessr'
                game_state.game_data = '{}'
            db.session.commit()
            print("Database updated successfully")

            # Initialize geo_guessr game
            print("Initializing geo_guessr game...")
            from games.geo_guessr import GeoGuessrGame

            # Create game instance with location and media URL
            geo_game = GeoGuessrGame(
                socketio,
                location_data=location.to_dict(),
                media_url=session_question.question.media_url
            )

            # Set as active game
            game_manager.active_game = geo_game

            # Initialize the game
            geo_game.initialize()

            # Forward players to geo_guessr page
            emit('forward_to_geo_guessr', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict
            }, broadcast=True)

            # Trigger display redirect
            emit('game_started', {'game': 'geo_guessr'}, broadcast=True)

            print(f"Question selected: Category {category_position}, Value {question_value} (GeoGuessr)")
            print("Players and display forwarded to geo_guessr interface")
        # Check if this is a match me question
        elif session_question.question.question_type == 'mm':
            # Get the category data for this question
            from models.game import MatchMeCategory
            category = MatchMeCategory.query.filter_by(question_id=session_question.question.id).first()

            if not category:
                emit('error', {'message': 'No category found for this match_me question'})
                return

            # Update game state in database
            print("Updating game state in database for match_me...")
            game_state = GameState.query.first()
            if not game_state:
                game_state = GameState(is_active=True, active_game='match_me')
                db.session.add(game_state)
            else:
                game_state.is_active = True
                game_state.active_game = 'match_me'
                game_state.game_data = '{}'
            db.session.commit()
            print("Database updated successfully")

            # Initialize match_me game
            print("Initializing match_me game...")
            from games.match_me import MatchMeGame

            # Create game instance with category ID and question text
            match_me_game = MatchMeGame(
                socketio,
                category_id=category.id,
                question_text=session_question.question.question_text
            )

            # Set as active game
            game_manager.active_game = match_me_game

            # Initialize the game
            match_me_game.initialize()

            # Emit question_selected for Admin Panel and Players (but not Display)
            # This prevents the display from showing the standard question card before redirecting
            question_data = {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'answer': answer_to_display,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }
            
            emit('question_selected', question_data, room='admin')
            
            # Send to all players individually
            users = User.query.filter(User.username != 'admin').all()
            for user in users:
                emit('question_selected', question_data, room=user.username)

            # Forward players to match_me page
            emit('forward_to_match_me', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict
            }, broadcast=True)

            # Trigger display redirect
            emit('game_started', {'game': 'match_me'}, broadcast=True)

            print(f"Question selected: Category {category_position}, Value {question_value} (MatchMe)")
            print("Players and display forwarded to match_me interface")
        # Check if this is a puzzle question
        elif session_question.question.question_type == 'puzzle':
            # Update game state in database
            print("Updating game state in database for coop_puzzle...")
            game_state = GameState.query.first()
            if not game_state:
                game_state = GameState(is_active=True, active_game='coop_puzzle')
                db.session.add(game_state)
            else:
                game_state.is_active = True
                game_state.active_game = 'coop_puzzle'
                game_state.game_data = '{}'
            db.session.commit()
            print("Database updated successfully")

            # Initialize coop_puzzle game
            print("Initializing coop_puzzle game...")
            from games.coop_puzzle import CoopPuzzleGame

            # Create game instance with media URL from question
            puzzle_game = CoopPuzzleGame(
                socketio,
                media_url=session_question.question.media_url
            )

            # Set as active game
            game_manager.active_game = puzzle_game

            # Initialize the game
            puzzle_game.initialize()

            # Forward players to coop_puzzle page
            emit('forward_to_coop_puzzle', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict
            }, broadcast=True)

            # Trigger display redirect
            emit('game_started', {'game': 'coop_puzzle'}, broadcast=True)

            print(f"Question selected: Category {category_position}, Value {question_value} (Puzzle)")
            print("Players and display forwarded to coop_puzzle interface")
        # Check if this is a price guesser question
        elif session_question.question.question_type == 'pg':
            # Initialize price_guesser game (registers socket events)
            print("Initializing price_guesser game...")
            game_manager.start_game('price_guesser')

            # Forward players to price guesser page
            emit('forward_to_price_guesser', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict
            }, broadcast=True)

            # Trigger product selection in price_guesser game
            # This event will now be received because we just registered the handlers
            emit('pg_question_selected', {
                'question_text': session_question.question.question_text
            })

            # Trigger display redirect
            emit('game_started', {'game': 'price_guesser'}, broadcast=True)

            print(f"Question selected: Category {category_position}, Value {question_value} (Price Guesser)")
            print("Display forwarded to price guesser interface")
        # Check if this is a This or That question
        elif session_question.question.question_type == 'tt':
            # Emit question_selected for admin panel and game board display
            emit('question_selected', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'answer': answer_to_display,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }, broadcast=True)

            # Initialize This or That (registers socket events)
            print("Initializing This or That...")
            game_manager.start_game('tt')

            # Forward players to This or That page
            emit('forward_to_sorting_game', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict
            }, broadcast=True)

            # Game is initialized, waiting for admin to click "Start Game"
            print(f"Question selected: Category {category_position}, Value {question_value} (This or That)")
            print("Players forwarded to This or That interface, waiting for admin to start")
        # Check if this is a multiple choice question
        elif session_question.question.question_type == 'mc':
            emit('question_selected', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'answer': answer_to_display,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }, broadcast=True)

            emit('forward_to_mc', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'questionData': question_dict
            }, broadcast=True)

            print(f"Question selected: Category {category_position}, Value {question_value} (Multiple Choice)")
            print("Players forwarded to multiple choice interface")
        # Check if this question expects input from players
        elif session_question.question.input_expected:
            print(f"DEBUG: Checking input question routing:")
            print(f"  - movie_id: {session_question.question.movie_id}")
            print(f"  - question_type from DB model: '{session_question.question.question_type}' (type: {type(session_question.question.question_type)})")
            print(f"  - question_type == 'ac': {session_question.question.question_type == 'ac'}")

            # Emit question_selected for game board display
            emit('question_selected', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'answer': answer_to_display,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }, broadcast=True)

            # Check if this is a movie question - forward to movie_guesser page
            if session_question.question.movie_id:
                emit('forward_to_movie_guesser', {
                    'category': category_position,
                    'value': question_value,
                    'question': session_question.question.question_text,
                    'questionData': question_dict,
                    'currentItemIndex': current_item_index,
                    'totalItems': total_items
                }, broadcast=True)

                print(f"Question selected: Category {category_position}, Value {question_value} (Movie Question)")
                print("Players forwarded to movie guesser interface")
            # Check if this is a Top 5 auto-complete question (question_type = 'ac')
            elif session_question.question.question_type == 'ac':
                emit('forward_to_top_5', {
                    'category': category_position,
                    'value': question_value,
                    'question': session_question.question.question_text,
                    'questionData': question_dict,
                    'previousGuesses': []  # Empty for new question
                }, broadcast=True)

                print(f"Question selected: Category {category_position}, Value {question_value} (Top 5)")
                print("Players forwarded to Top 5 interface")
            else:
                # Forward players to question input interface
                emit('forward_to_input', {
                    'category': category_position,
                    'value': question_value,
                    'question': session_question.question.question_text,
                    'questionData': question_dict
                }, broadcast=True)

                print(f"Question selected: Category {category_position}, Value {question_value} (Input Expected)")
                print("Players forwarded to question input interface")
        else:
            # Check if this question type should use buzzer
            question_type = session_question.question.question_type
            buzzer_question_types = ['text', 'image', 'audio', 'video', 'silhouette', 'fg']

            # Emit question_selected for game board display
            emit('question_selected', {
                'category': category_position,
                'value': question_value,
                'question': session_question.question.question_text,
                'answer': answer_to_display,
                'questionData': question_dict,
                'currentItemIndex': current_item_index,
                'totalItems': total_items
            }, broadcast=True)

            if question_type in buzzer_question_types:
                # Forward players to buzzer interface for these question types
                emit('forward_to_buzzer', {
                    'category': category_position,
                    'value': question_value,
                    'question': session_question.question.question_text,
                    'questionData': session_question.question.to_dict()
                }, broadcast=True)
                print(f"Question selected: Category {category_position}, Value {question_value} (Type: {question_type})")
                print("Players forwarded to buzzer interface")
            else:
                print(f"Question selected: Category {category_position}, Value {question_value} (Type: {question_type})")
                print("Question type does not use buzzer - players remain on current page")
        
    except Exception as e:
        print(f"Error selecting question: {e}")
        emit('error', {'message': 'Error selecting question'})


@socketio.on('next_item')
def handle_next_item():
    """Handle admin navigation to next item/group in question with multiple item_order values"""
    global current_question_data, current_item_index, total_items

    if 'username' not in session or session['username'] != 'admin':
        return

    # Check if question has items with multiple distinct item_order values
    if not current_question_data or total_items <= 1:
        emit('error', {'message': 'No items to navigate'})
        return

    # Check bounds
    if current_item_index >= total_items - 1:
        print(f"Already at last item ({current_item_index + 1}/{total_items})")
        return

    # Increment index
    current_item_index += 1
    print(f"Moving to item {current_item_index + 1}/{total_items}")

    # Emit update to all clients
    emit('item_changed', {
        'currentItemIndex': current_item_index,
        'totalItems': total_items,
        'questionData': current_question_data
    }, broadcast=True)


@socketio.on('previous_item')
def handle_previous_item():
    """Handle admin navigation to previous item/group in question with multiple item_order values"""
    global current_question_data, current_item_index, total_items

    if 'username' not in session or session['username'] != 'admin':
        return

    # Check if question has items with multiple distinct item_order values
    if not current_question_data or total_items <= 1:
        emit('error', {'message': 'No items to navigate'})
        return

    # Check bounds
    if current_item_index <= 0:
        print(f"Already at first item (1/{total_items})")
        return

    # Decrement index
    current_item_index -= 1
    print(f"Moving to item {current_item_index + 1}/{total_items}")

    # Emit update to all clients
    emit('item_changed', {
        'currentItemIndex': current_item_index,
        'totalItems': total_items,
        'questionData': current_question_data
    }, broadcast=True)


@socketio.on('request_input_question')
def handle_request_input_question():
    """Send current input question to a player who just connected"""
    global current_question_data

    if 'username' not in session or session['username'] == 'admin':
        return

    # If there's a current question and it expects input, send it
    if current_question_data and current_question_data.get('input_expected'):
        emit('question_selected', {
            'question': current_question_data.get('question_text'),
            'questionData': current_question_data
        })
        print(f"Sent current input question to {session['username']}")


@socketio.on('request_mc_question')
def handle_request_mc_question():
    """Send current MC question to a player who just connected"""
    global current_question_data

    if 'username' not in session or session['username'] == 'admin':
        return

    if current_question_data and current_question_data.get('question_type') == 'mc':
        emit('forward_to_mc', {
            'question': current_question_data.get('question_text'),
            'questionData': current_question_data
        })
        print(f"Sent current MC question to {session['username']}")


@socketio.on('submit_mc_answer')
def handle_submit_mc_answer(data):
    """Handle player answer submission for multiple choice questions"""
    from models.game import AnswerUser, Question, AnswerExpected, QuestionItem

    if 'username' not in session or session['username'] == 'admin':
        emit('answer_submitted', {'success': False, 'message': 'Invalid user'})
        return

    try:
        question_id = int(data['question_id'])
        submitted_item_id = int(data['item_id'])

        # Get user
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            emit('answer_submitted', {'success': False, 'message': 'User not found'})
            return

        # Get question
        question = Question.query.filter_by(id=question_id).first()
        if not question or question.question_type != 'mc':
            emit('answer_submitted', {'success': False, 'message': 'Question not found'})
            return

        # Check if player already submitted for this question
        existing_answer = AnswerUser.query.filter_by(
            user_id=user.id,
            question_id=question_id
        ).first()

        if existing_answer:
            emit('answer_submitted', {'success': False, 'message': 'You have already answered this question!'})
            return

        # Look up the selected option to get its text
        selected_item = QuestionItem.query.filter_by(id=submitted_item_id, question_id=question_id).first()
        if not selected_item:
            emit('answer_submitted', {'success': False, 'message': 'Invalid option selected'})
            return

        # Check correctness by comparing item_id against answers_expected
        expected = AnswerExpected.query.filter_by(question_id=question_id).first()
        is_correct = expected is not None and expected.item_id == submitted_item_id

        # Store answer
        new_answer = AnswerUser(
            user_id=user.id,
            question_id=question_id,
            round=1,
            answer_raw=selected_item.item_text,
            answer_normalized=selected_item.item_text.lower().strip(),
            is_correct=is_correct
        )
        db.session.add(new_answer)
        db.session.commit()

        print(f"MC answer submitted by {user.username}: {selected_item.item_text} (item_id={submitted_item_id}) - Correct: {is_correct}")

        # Notify admin of new submission (no correctness info)
        total_submissions = AnswerUser.query.filter_by(question_id=question_id).count()
        emit('input_answer_received', {
            'question_id': question_id,
            'username': user.username,
            'total_submissions': total_submissions
        }, broadcast=True, include_self=False)

        # Confirm submission to player without revealing correctness
        emit('answer_submitted', {'success': True, 'message': 'Answer recorded!'})

    except Exception as e:
        print(f"Error submitting MC answer: {e}")
        emit('answer_submitted', {'success': False, 'message': 'Error submitting answer'})


@socketio.on('submit_answer')
def handle_submit_answer(data):
    """Handle player answer submission for input questions"""
    from models.game import AnswerUser, Question, Movie
    from answer_handler import AnswerHandler

    if 'username' not in session or session['username'] == 'admin':
        emit('answer_submitted', {'success': False, 'message': 'Invalid user'})
        return

    try:
        question_id = int(data['question_id'])
        answer_raw = data['answer'].strip()
        round_num = int(data.get('round', 1))  # Get round number from client (1-based)
        submitted_movie_id = data.get('movie_id')  # Get movie ID if user selected from dropdown

        if not answer_raw:
            emit('answer_submitted', {'success': False, 'message': 'Answer cannot be empty'})
            return

        # Get user
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            emit('answer_submitted', {'success': False, 'message': 'User not found'})
            return

        # Get question to check if it's a movie question
        question = Question.query.filter_by(id=question_id).first()
        if not question:
            emit('answer_submitted', {'success': False, 'message': 'Question not found'})
            return

        # Normalize answer
        answer_normalized = AnswerHandler.normalize_answer(answer_raw)

        # Check if player already answered correctly for this question (any round)
        correct_answer = AnswerUser.query.filter_by(
            user_id=user.id,
            question_id=question_id,
            is_correct=True
        ).first()

        if correct_answer:
            # Player already guessed correctly - reject further submissions
            emit('answer_submitted', {
                'success': False,
                'message': f'You already guessed correctly in round {correct_answer.round}!'
            })
            return

        # Check if user already submitted an answer for this question and round
        existing_answer = AnswerUser.query.filter_by(
            user_id=user.id,
            question_id=question_id,
            round=round_num
        ).first()

        if existing_answer:
            # Player already answered for this round - reject
            emit('answer_submitted', {
                'success': False,
                'message': 'You have already answered for this round!'
            })
            return

        # Determine if answer is correct
        is_correct = False
        if question.movie_id:
            # Movie question - validate immediately
            movie = Movie.query.filter_by(id=question.movie_id).first()
            if movie:
                # If user selected from dropdown (movie_id provided), compare IDs directly
                if submitted_movie_id is not None:
                    is_correct = (int(submitted_movie_id) == movie.id)
                    print(f"Movie answer validation (ID comparison): submitted_movie_id={submitted_movie_id} vs expected_movie_id={movie.id} - Correct: {is_correct}")
                else:
                    # User typed answer manually - use fuzzy matching
                    is_correct, similarity = AnswerHandler.check_movie_answer(
                        answer_normalized,
                        movie.title
                    )
                    print(f"Movie answer validation (text comparison): '{answer_raw}' vs '{movie.title}' - Correct: {is_correct} (Similarity: {similarity:.1f}%)")

        # Create new answer
        new_answer = AnswerUser(
            user_id=user.id,
            question_id=question_id,
            round=round_num,
            answer_raw=answer_raw,
            answer_normalized=answer_normalized,
            is_correct=is_correct
        )
        db.session.add(new_answer)

        db.session.commit()

        print(f"Answer submitted by {user.username}: {answer_raw} (normalized: {answer_normalized}) - Correct: {is_correct}")

        # Notify admin of new submission
        total_submissions = AnswerUser.query.filter_by(question_id=question_id).count()
        emit('input_answer_received', {
            'question_id': question_id,
            'username': user.username,
            'total_submissions': total_submissions
        }, broadcast=True, include_self=False)

        # If answer is correct, broadcast to display
        if is_correct:
            emit('player_guessed_correct', {
                'question_id': question_id,
                'username': user.username,
                'round': round_num,
                'answer': answer_raw
            }, broadcast=True)

        emit('answer_submitted', {'success': True, 'message': 'Answer recorded!', 'is_correct': is_correct})

    except Exception as e:
        print(f"Error submitting answer: {e}")
        emit('answer_submitted', {'success': False, 'message': 'Error submitting answer'})


@socketio.on('submit_top_5_answer')
def handle_submit_top_5_answer(data):
    """Handle player answer submission for Top 5 auto-complete questions"""
    from models.game import AnswerUser, Question
    from answer_handler import AnswerHandler

    if 'username' not in session or session['username'] == 'admin':
        emit('top_5_answer_submitted', {'success': False, 'message': 'Invalid user'})
        return

    try:
        question_id = int(data['question_id'])
        answer_raw = data['answer'].strip()

        if not answer_raw:
            emit('top_5_answer_submitted', {'success': False, 'message': 'Answer cannot be empty'})
            return

        # Get user
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            emit('top_5_answer_submitted', {'success': False, 'message': 'User not found'})
            return

        # Get question
        question = Question.query.filter_by(id=question_id).first()
        if not question:
            emit('top_5_answer_submitted', {'success': False, 'message': 'Question not found'})
            return

        # Count how many answers this player has already submitted for this question
        existing_answers_count = AnswerUser.query.filter_by(
            user_id=user.id,
            question_id=question_id
        ).count()

        print(f"DEBUG Top 5: User {user.username} (ID {user.id}) has {existing_answers_count} existing answers for question {question_id}")

        # Check if player has already submitted 5 answers
        if existing_answers_count >= 5:
            emit('top_5_answer_submitted', {
                'success': False,
                'message': 'You have already submitted 5 guesses!'
            })
            return

        # Normalize answer
        answer_normalized = AnswerHandler.normalize_answer(answer_raw)

        # Check for duplicate submission (case-insensitive)
        duplicate = AnswerUser.query.filter_by(
            user_id=user.id,
            question_id=question_id
        ).filter(
            db.func.lower(AnswerUser.answer_normalized) == answer_normalized.lower()
        ).first()

        if duplicate:
            emit('top_5_answer_submitted', {
                'success': False,
                'message': 'You already submitted this answer!'
            })
            return

        # Create new answer (round = submission number, 1-5)
        round_num = existing_answers_count + 1
        new_answer = AnswerUser(
            user_id=user.id,
            question_id=question_id,
            round=round_num,
            answer_raw=answer_raw,
            answer_normalized=answer_normalized,
            is_correct=False  # Will be evaluated when admin reveals
        )
        db.session.add(new_answer)
        db.session.commit()

        print(f"DEBUG Top 5: Successfully saved answer {round_num}/5 by {user.username} (ID {user.id}) for question {question_id}: {answer_raw}")

        # Notify admin of new submission
        emit('top_5_answer_received', {
            'question_id': question_id,
            'username': user.username,
            'answer': answer_raw,
            'guess_number': round_num
        }, broadcast=True, include_self=False)

        emit('top_5_answer_submitted', {'success': True, 'message': f'Guess {round_num} recorded!'})

    except Exception as e:
        print(f"Error submitting Top 5 answer: {e}")
        emit('top_5_answer_submitted', {'success': False, 'message': 'Error submitting answer'})


@socketio.on('close_input_round')
def handle_close_input_round(data):
    """Handle admin closing an input question round and calculating results"""
    from models.game import Question, AnswerExpected, AnswerUser
    from answer_handler import AnswerHandler

    if 'username' not in session or session['username'] != 'admin':
        return

    try:
        question_id = int(data['question_id'])

        # Evaluate all answers
        results = AnswerHandler.evaluate_all_answers(question_id, db.session)

        if 'error' in results:
            emit('error', {'message': results['error']})
            return

        # Add usernames to results
        for user_result in results['user_results']:
            user = User.query.filter_by(id=user_result['user_id']).first()
            if user:
                user_result['username'] = user.username

        # Award points to winners/correct answerers
        if results['input_type'] == 'guess':
            # Award points to all winners (closest guesses)
            for user_result in results['user_results']:
                if user_result.get('is_winner'):
                    user = User.query.filter_by(id=user_result['user_id']).first()
                    if user:
                        user.overall_score += 1
                        user_result['new_score'] = user.overall_score
        elif results['input_type'] == 'movie':
            # Award points based on round (early guesses get more points)
            for user_result in results['user_results']:
                if user_result.get('is_correct'):
                    round_num = user_result.get('round', 1)

                    # Determine points based on round
                    if round_num == 1:
                        points = 3
                    elif round_num in [2, 3]:
                        points = 2
                    elif round_num in [4, 5]:
                        points = 1
                    else:
                        points = 0  # No points for rounds beyond 5

                    user = User.query.filter_by(id=user_result['user_id']).first()
                    if user:
                        user.overall_score += points
                        user_result['new_score'] = user.overall_score
                        user_result['points_earned'] = points  # Add to results for display
        else:
            # Award points to all correct answers (normal text questions)
            for user_result in results['user_results']:
                if user_result.get('is_correct'):
                    user = User.query.filter_by(id=user_result['user_id']).first()
                    if user:
                        user.overall_score += 1
                        user_result['new_score'] = user.overall_score

        db.session.commit()

        # Broadcast results to all clients
        emit('input_question_results', results, broadcast=True)

        print(f"Input round closed for question {question_id}")
        print(f"Results: {results['total_submissions']} submissions")

    except Exception as e:
        print(f"Error closing input round: {e}")
        emit('error', {'message': 'Error closing input round'})


@socketio.on('reveal_top_5')
def handle_reveal_top_5(data):
    """Handle admin revealing Top 5 results and calculating scores"""
    from models.game import Question, AnswerExpected, AnswerUser
    from answer_handler import AnswerHandler

    print(f"DEBUG: reveal_top_5 handler called with data: {data}")

    if 'username' not in session or session['username'] != 'admin':
        print("DEBUG: Not admin, ignoring")
        return

    try:
        question_id = int(data['question_id'])
        print(f"DEBUG: Revealing Top 5 results for question {question_id}")

        # Get question and expected answers
        question = Question.query.filter_by(id=question_id).first()
        if not question:
            emit('error', {'message': 'Question not found'})
            return

        expected_answers = AnswerExpected.query.filter_by(question_id=question_id).all()
        if not expected_answers:
            emit('error', {'message': 'No expected answers found'})
            return

        # Get all player submissions for this question
        all_submissions = AnswerUser.query.filter_by(question_id=question_id).all()

        # Normalize expected answers for comparison
        expected_normalized = {ans.rank: ans.answer_normalized for ans in expected_answers}

        # Organize submissions by player
        player_results = {}
        for submission in all_submissions:
            user_id = submission.user_id
            if user_id not in player_results:
                player_results[user_id] = {
                    'user_id': user_id,
                    'guesses': []
                }

            # Check if this answer matches any expected answer using fuzzy matching
            is_correct = False
            matched_rank = None

            for rank, expected_norm in expected_normalized.items():
                is_match, similarity, matched_text = AnswerHandler.calculate_text_correctness(
                    submission.answer_normalized,
                    [expected_norm]
                )

                if is_match:
                    is_correct = True
                    matched_rank = rank
                    break

            # Add guess to player's results
            player_results[user_id]['guesses'].append({
                'answer_raw': submission.answer_raw,
                'answer_normalized': submission.answer_normalized,
                'is_correct': is_correct,
                'matched_rank': matched_rank,
                'round': submission.round
            })

            # Update is_correct in database
            submission.is_correct = is_correct

        # Add username and calculate correct_count for each player
        for user_id, result in player_results.items():
            user = User.query.filter_by(id=user_id).first()
            if user:
                result['username'] = user.username
                result['correct_count'] = sum(1 for g in result['guesses'] if g['is_correct'])
                result['points_earned'] = 0

        # Find the highest correct_count
        max_correct = max((r.get('correct_count', 0) for r in player_results.values()), default=0)

        # Award 1 point only to player(s) with the highest correct_count
        if max_correct > 0:
            for user_id, result in player_results.items():
                if result.get('correct_count', 0) == max_correct:
                    user = User.query.filter_by(id=user_id).first()
                    if user:
                        user.overall_score += 1
                        result['points_earned'] = 1
                        result['new_score'] = user.overall_score

        db.session.commit()

        # Prepare results for broadcast
        results = {
            'question_id': question_id,
            'expected_answers': [
                {
                    'rank': ans.rank,
                    'answer_raw': ans.answer_raw,
                    'answer_normalized': ans.answer_normalized
                }
                for ans in expected_answers
            ],
            'player_results': [
                {
                    'username': result['username'],
                    'guesses': result['guesses'],
                    'points_earned': result.get('points_earned', 0),
                    'new_score': result.get('new_score', 0)
                }
                for result in player_results.values()
            ]
        }

        # Broadcast results to all clients
        print(f"DEBUG: Broadcasting top_5_results event to all clients")
        print(f"DEBUG: Results data: {results}")
        emit('top_5_results', results, broadcast=True)

        print(f"Top 5 results revealed for question {question_id}")
        print(f"Total players: {len(player_results)}")

    except Exception as e:
        print(f"Error revealing Top 5 results: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': 'Error revealing Top 5 results'})


@socketio.on('get_board_state')
def handle_get_board_state():
    """Send current board state to client"""
    try:
        # Get the configured active session
        session_setup = get_active_session()
        if not session_setup:
            emit('game_board_state', {'questions': {}})
            return
        
        # Build the board state
        board_state = {'questions': {}}
        
        for session_category in session_setup.session_categories:
            for session_question in session_category.selected_questions:
                if session_question.used:
                    key = f"{session_category.position}-{session_question.position * 100}"
                    board_state['questions'][key] = True
        
        emit('game_board_state', board_state)
        
    except Exception as e:
        print(f"Error getting board state: {e}")
        emit('game_board_state', {'questions': {}})

@socketio.on('admin_media_control')
def handle_admin_media_control(data):
    """Handle media control events from admin and broadcast to display"""
    if 'username' in session and session['username'] == 'admin':
        action = data.get('action')
        media_type = data.get('mediaType')
        track_id = data.get('trackId')  # For Spotify tracks
        
        print(f"Admin media control: {action} for {media_type} (track: {track_id})")
        
        # Handle Spotify tracks directly on the server
        if media_type == 'audio' and track_id:
            try:
                handle_spotify_control(action, track_id)
                print(f"Spotify control executed: {action} for track {track_id}")
            except Exception as e:
                print(f"Spotify control failed: {e}")
                # Continue to broadcast even if Spotify fails
        
        # Always broadcast to display clients (for both regular media and Spotify status updates)
        emit('admin_media_control', {
            'action': action,
            'mediaType': media_type,
            'trackId': track_id
        }, broadcast=True)
        
        print(f"Broadcasted admin_media_control: {action} {media_type} trackId={track_id}")
    else:
        print("Non-admin attempted to control media")

@socketio.on('admin_reveal_question')
def handle_admin_reveal_question():
    """Handle admin revealing question content on display"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin revealing question content on display")

        # Check if we're in a price_guesser game that needs scraping
        game_state = GameState.query.first()
        if game_state and game_state.active_game == 'price_guesser':
            # Check if scraping already happened
            active_game = game_manager.get_active_game()
            if active_game:
                current_state = active_game.get_game_state()
                scraping_status = current_state.get('scraping_status', 'not_started')

                if scraping_status == 'not_started':
                    print("Price Guesser detected - starting deferred scraping now...")
                    print("Calling show_next_product() to scrape Amazon data...")
                    # This will block for 2-4 seconds, but that's OK - happens when admin clicks
                    active_game.show_next_product()
                    print("Scraping complete!")

                    # Mark scraping as complete
                    active_game.update_game_state({'scraping_status': 'complete'})
                else:
                    print("Scraping already complete - just revealing content")
            else:
                print("ERROR: Active game not found")

        # Broadcast to all clients (especially displays)
        emit('reveal_question', {}, broadcast=True)
    else:
        print("Non-admin attempted to reveal question")

@socketio.on('buzzer_buzz')
def handle_buzzer_buzz():
    """Handle player buzzing in"""
    global current_buzzed_player, current_question_data
    if 'username' in session and session['username'] != 'admin':
        username = session['username']
        print(f"Player {username} buzzed in")

        # Store the buzzed player globally for scoring
        current_buzzed_player = username

        # Broadcast to all clients that this player buzzed
        emit('buzzer_player_buzzed', {
            'username': username
        }, broadcast=True)

        # If this is a silhouette question, auto-pause the growth
        if current_question_data and current_question_data.get('question_type') == 'silhouette':
            print("Auto-pausing silhouette growth due to buzz")
            emit('silhouette_pause_growth', broadcast=True)

        # If this is a font guesser question, auto-pause the animation
        if current_question_data and current_question_data.get('question_type') == 'fg':
            global fg_is_running
            print("Auto-pausing font guesser animation due to buzz")
            fg_is_running = False
            emit('fg_paused', broadcast=True)

@socketio.on('buzzer_reset')
def handle_buzzer_reset():
    """Handle admin resetting the buzzer"""
    global current_buzzed_player
    if 'username' in session and session['username'] == 'admin':
        print("Admin reset the buzzer")
        current_buzzed_player = None  # Clear the buzzed player
        emit('buzzer_reset', broadcast=True)

@socketio.on('buzzer_correct')
def handle_buzzer_correct():
    """Handle admin marking answer as correct"""
    global current_buzzed_player, current_question_data, silhouette_phase
    if 'username' in session and session['username'] == 'admin':
        print("Admin marked answer as correct")

        if current_buzzed_player:
            # Find the user and update their score
            user = User.query.filter_by(username=current_buzzed_player).first()
            if user:
                # Determine points to award
                points_to_award = 1  # Default

                # Check if this is a silhouette question
                if current_question_data and current_question_data.get('question_type') == 'silhouette':
                    # Award 2 points if in growing phase, 1 point if in color reveal phase
                    if silhouette_phase == 'growing':
                        points_to_award = 2
                        print(f"Silhouette question in growing phase - awarding 2 points")
                    elif silhouette_phase == 'revealing_color':
                        points_to_award = 1
                        print(f"Silhouette question in color reveal phase - awarding 1 point")
                    else:
                        points_to_award = 1
                        print(f"Silhouette question in unknown phase '{silhouette_phase}' - awarding 1 point")

                user.overall_score += points_to_award
                db.session.commit()
                print(f"Awarded {points_to_award} point(s) to {current_buzzed_player}. New score: {user.overall_score}")

                # Broadcast the result with updated score
                emit('buzzer_answer_correct', {
                    'username': current_buzzed_player,
                    'new_score': user.overall_score,
                    'points_awarded': points_to_award
                }, broadcast=True)

                # Clear the buzzed player
                current_buzzed_player = None
            else:
                print(f"User {current_buzzed_player} not found for scoring")
                emit('buzzer_answer_correct', broadcast=True)
                current_buzzed_player = None
        else:
            print("No buzzed player found for scoring")
            emit('buzzer_answer_correct', broadcast=True)

@socketio.on('buzzer_wrong')
def handle_buzzer_wrong():
    """Handle admin marking answer as wrong"""
    global current_buzzed_player, current_question_data, silhouette_phase
    if 'username' in session and session['username'] == 'admin':
        print("Admin marked answer as wrong")

        if current_buzzed_player:
            # Find the user and update their score
            user = User.query.filter_by(username=current_buzzed_player).first()
            if user:
                # Determine points to deduct
                points_to_deduct = 1  # Default

                # Check if this is a silhouette question
                if current_question_data and current_question_data.get('question_type') == 'silhouette':
                    # Deduct 2 points if in growing phase, 1 point if in color reveal phase
                    if silhouette_phase == 'growing':
                        points_to_deduct = 2
                        print(f"Silhouette question in growing phase - deducting 2 points")
                    elif silhouette_phase == 'revealing_color':
                        points_to_deduct = 1
                        print(f"Silhouette question in color reveal phase - deducting 1 point")
                    else:
                        points_to_deduct = 1
                        print(f"Silhouette question in unknown phase '{silhouette_phase}' - deducting 1 point")

                # Deduct points but don't go below 0
                old_score = user.overall_score
                user.overall_score = max(0, user.overall_score - points_to_deduct)
                db.session.commit()
                print(f"Deducted {points_to_deduct} point(s) from {current_buzzed_player}. Old score: {old_score}, New score: {user.overall_score}")

                # Broadcast the result with updated score
                emit('buzzer_answer_wrong', {
                    'username': current_buzzed_player,
                    'new_score': user.overall_score,
                    'points_deducted': points_to_deduct
                }, broadcast=True)

                # Clear the buzzed player
                current_buzzed_player = None
            else:
                print(f"User {current_buzzed_player} not found for scoring")
                emit('buzzer_answer_wrong', broadcast=True)
                current_buzzed_player = None
        else:
            print("No buzzed player found for scoring")
            emit('buzzer_answer_wrong', broadcast=True)

@socketio.on('silhouette_start_growth')
def handle_silhouette_start_growth():
    """Handle admin starting silhouette growth animation"""
    global silhouette_phase
    if 'username' in session and session['username'] == 'admin':
        print("Admin started silhouette growth")
        silhouette_phase = 'growing'
        emit('silhouette_start_growth', broadcast=True)

@socketio.on('silhouette_pause_growth')
def handle_silhouette_pause_growth():
    """Handle admin pausing silhouette growth animation"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin paused silhouette growth")
        emit('silhouette_pause_growth', broadcast=True)

@socketio.on('silhouette_resume_growth')
def handle_silhouette_resume_growth():
    """Handle admin resuming silhouette growth animation"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin resumed silhouette growth")
        emit('silhouette_resume_growth', broadcast=True)

@socketio.on('silhouette_color_reveal_started')
def handle_silhouette_color_reveal_started():
    """Handle notification that color reveal phase has started"""
    global silhouette_phase
    print("Silhouette color reveal phase started")
    silhouette_phase = 'revealing_color'

@socketio.on('silhouette_reveal')
def handle_silhouette_reveal():
    """Handle admin revealing the silhouette answer"""
    global silhouette_phase
    if 'username' in session and session['username'] == 'admin':
        print("Admin revealed silhouette answer")
        silhouette_phase = 'complete'
        # Get answer from current question data
        global current_question_data
        answer_text = ""
        if current_question_data and current_question_data.get('expected_answers'):
            # Get all expected answers
            answers = current_question_data.get('expected_answers', [])
            if answers:
                answer_texts = [ans.get('answer_raw', '') for ans in answers if ans.get('answer_raw')]
                answer_text = ' / '.join(answer_texts)

        emit('silhouette_reveal', {
            'answer': answer_text
        }, broadcast=True)

# Font Guesser state
fg_target = ''
fg_current_chars = []
fg_space_indices = []
fg_is_running = False
fg_swap_interval = 2.5

def fg_get_random_wrong_index():
    """Find a random index where current char doesn't match target (excluding spaces)"""
    global fg_current_chars, fg_target, fg_space_indices
    wrong_indices = [
        i for i, c in enumerate(fg_current_chars)
        if i not in fg_space_indices and c != fg_target[i]
    ]
    if not wrong_indices:
        return None
    return random.choice(wrong_indices)

def fg_find_char_position(char, exclude_index):
    """Find where a specific character is currently located, excluding a given index.
    Only returns positions where the character is MISPLACED (not already correct),
    to avoid moving letters that are already in their final position."""
    global fg_current_chars, fg_space_indices, fg_target
    for i, c in enumerate(fg_current_chars):
        if i != exclude_index and i not in fg_space_indices and c == char:
            # Only return this position if the character here is misplaced
            # (i.e., it doesn't match what should be at this position)
            if c != fg_target[i]:
                return i
    return None

def fg_perform_swap():
    """Pick a random wrong position and swap with the correct letter's current location"""
    global fg_current_chars, fg_target, fg_is_running

    idx_a = fg_get_random_wrong_index()

    if idx_a is None:
        socketio.emit('fg_complete', {'message': 'Word revealed!'})
        fg_is_running = False
        return False

    needed_char = fg_target[idx_a]
    idx_b = fg_find_char_position(needed_char, idx_a)

    if idx_b is None:
        fg_is_running = False
        return False

    fg_current_chars[idx_a], fg_current_chars[idx_b] = fg_current_chars[idx_b], fg_current_chars[idx_a]

    socketio.emit('fg_swap', {
        'indexA': idx_a,
        'indexB': idx_b
    })

    print(f"Font Guesser swap: {idx_a} <-> {idx_b}, current: {''.join(fg_current_chars)}")
    return True

def fg_game_loop():
    """Background task that triggers swaps at intervals"""
    global fg_is_running, fg_swap_interval
    while fg_is_running:
        socketio.sleep(fg_swap_interval)
        if fg_is_running:
            if not fg_perform_swap():
                break

@socketio.on('fg_init')
def handle_fg_init(data):
    """Initialize font guesser with target text and font URL"""
    global fg_target, fg_current_chars, fg_space_indices, fg_is_running

    if 'username' not in session or session['username'] != 'admin':
        return

    target = data.get('target', '').upper()
    font_url = data.get('font_url', '')

    if not target:
        print("Font Guesser: No target text provided")
        return

    fg_target = target
    fg_is_running = False

    fg_space_indices = [i for i, c in enumerate(fg_target) if c == ' ']

    non_space_chars = [c for c in fg_target if c != ' ']
    random.shuffle(non_space_chars)

    fg_current_chars = []
    non_space_idx = 0
    for i, c in enumerate(fg_target):
        if c == ' ':
            fg_current_chars.append(' ')
        else:
            fg_current_chars.append(non_space_chars[non_space_idx])
            non_space_idx += 1

    emit('fg_init', {
        'chars': fg_current_chars,
        'font_url': font_url,
        'length': len(fg_target)
    }, broadcast=True)

    print(f"Font Guesser initialized: target='{fg_target}', shuffled={''.join(fg_current_chars)}")

@socketio.on('fg_start')
def handle_fg_start(data=None):
    """Start the font guesser swap animation"""
    global fg_is_running, fg_target

    if 'username' not in session or session['username'] != 'admin':
        return

    if not fg_target:
        print("Font Guesser: No target set, cannot start")
        return

    fg_is_running = True
    emit('fg_started', {}, broadcast=True)
    socketio.start_background_task(fg_game_loop)
    print("Font Guesser animation started")

@socketio.on('fg_pause')
def handle_fg_pause(data=None):
    """Pause the font guesser animation"""
    global fg_is_running

    if 'username' not in session or session['username'] != 'admin':
        return

    fg_is_running = False
    emit('fg_paused', {}, broadcast=True)
    print("Font Guesser animation paused")

@socketio.on('fg_resume')
def handle_fg_resume(data=None):
    """Resume the font guesser animation"""
    global fg_is_running, fg_target

    if 'username' not in session or session['username'] != 'admin':
        return

    if not fg_target:
        return

    fg_is_running = True
    emit('fg_resumed', {}, broadcast=True)
    socketio.start_background_task(fg_game_loop)
    print("Font Guesser animation resumed")

@socketio.on('fg_reveal')
def handle_fg_reveal(data=None):
    """Reveal the final answer"""
    global fg_is_running, fg_target, fg_current_chars

    if 'username' not in session or session['username'] != 'admin':
        return

    fg_is_running = False
    fg_current_chars = list(fg_target)

    emit('fg_reveal', {
        'answer': fg_target,
        'chars': fg_current_chars
    }, broadcast=True)

    print(f"Font Guesser answer revealed: {fg_target}")

@socketio.on('buzzer_reveal_answer')
def handle_buzzer_reveal_answer():
    """Handle admin revealing the answer for any buzzer question"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin revealed buzzer answer")
        global current_question_data
        answer_text = ""

        if current_question_data:
            # For MC questions, resolve answer from item_id
            if current_question_data.get('question_type') == 'mc':
                expected_answers = current_question_data.get('expected_answers', [])
                items = current_question_data.get('items', [])
                for ans in expected_answers:
                    item_id = ans.get('item_id')
                    if item_id:
                        matched_item = next((item for item in items if item.get('id') == item_id), None)
                        if matched_item:
                            answer_text = matched_item.get('item_text', '')
                            break
            else:
                # Try expected_answers first
                if current_question_data.get('expected_answers'):
                    answers = current_question_data.get('expected_answers', [])
                    if answers:
                        answer_texts = [ans.get('answer_raw', '') for ans in answers if ans.get('answer_raw')]
                        answer_text = ' / '.join(answer_texts)
                # Fallback to simple answer field
                if not answer_text and current_question_data.get('answer'):
                    answer_text = current_question_data.get('answer', '')

        print(f"Revealing answer: {answer_text}")
        emit('buzzer_reveal_answer', {
            'answer': answer_text
        }, broadcast=True)

@socketio.on('back_to_game_board')
def handle_back_to_game_board():
    """Handle admin sending players back to game board"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin sending players back to game board")

        # Clear current question data to prevent reconnection loop
        global current_question_data, current_item_index, total_items, silhouette_phase
        global fg_target, fg_current_chars, fg_space_indices, fg_is_running
        current_question_data = None
        current_item_index = 0
        total_items = 0
        silhouette_phase = 'idle'
        # Reset font guesser state
        fg_target = ''
        fg_current_chars = []
        fg_space_indices = []
        fg_is_running = False
        print("Cleared current question data")

        # End the current game if one is active
        if game_manager.active_game:
            print("Ending current game before going back to game board")
            game_manager.end_game()

        # Clear active game from database to prevent redirect loops
        game_state = GameState.query.first()
        if game_state:
            game_state.active_game = None
            game_state.game_data = '{}'
            db.session.commit()
            print("Game state cleared: active_game=None")

        emit('return_to_game_board', broadcast=True)

@socketio.on('admin_goto_game_board')
def handle_admin_goto_game_board():
    """Handle admin navigating to game board"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin navigating to game board")

        # Clear current question data to prevent reconnection loop
        global current_question_data, current_item_index, total_items
        current_question_data = None
        current_item_index = 0
        total_items = 0
        print("Cleared current question data")

        # End the current game if one is active
        if game_manager.active_game:
            print("Ending current game before navigating to game board")
            game_manager.end_game()

        # Update game state to show game board (platform active, no specific game)
        game_state = GameState.query.first()
        if game_state:
            game_state.is_active = True
            game_state.active_game = None
            game_state.game_data = '{}'
            db.session.commit()
            print("Game state updated: is_active=True, active_game=None")

        # Send display to game board
        emit('admin_display_goto_game_board', broadcast=True)
        # Send players to waiting room
        emit('admin_players_goto_waiting_room', broadcast=True)

@socketio.on('admin_goto_waiting_room')
def handle_admin_goto_waiting_room():
    """Handle admin navigating to waiting room"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin navigating to waiting room")

        # Clear current question data to prevent reconnection loop
        global current_question_data, current_item_index, total_items
        current_question_data = None
        current_item_index = 0
        total_items = 0
        print("Cleared current question data")

        # End the current game if one is active
        if game_manager.active_game:
            print("Ending current game before navigating to waiting room")
            game_manager.end_game()

        # Update game state to mark platform as inactive
        game_state = GameState.query.first()
        if game_state:
            game_state.is_active = False
            game_state.active_game = None
            game_state.game_data = '{}'
            db.session.commit()
            print("Game state updated: is_active=False, active_game=None")

        # Send both display and players to waiting room
        emit('admin_display_goto_waiting_room', broadcast=True)
        emit('admin_players_goto_waiting_room', broadcast=True)

# Price Guesser SocketIO handlers
@socketio.on('price_guesser_next_product')
def handle_price_guesser_next_product():
    """Admin requests next product"""
    if 'username' in session and session['username'] == 'admin':
        print("Admin requesting next product")

        # Get the active game instance
        active_game = game_manager.get_active_game()
        if active_game and hasattr(active_game, 'show_next_product'):
            active_game.show_next_product()
        else:
            print("No active price guesser game found")

@socketio.on('submit_price_guess')
@socketio.on('price_guesser_submit_guess')
def handle_price_guesser_submit_guess(data):
    """Handle player submitting a price guess"""
    from models.game import PriceGuessUser, Product

    if 'username' not in session or session['username'] == 'admin':
        emit('guess_submitted', {'success': False, 'message': 'Invalid user'})
        return

    try:
        product_id = int(data['product_id'])
        guess = data['guess']  # Already a number from frontend

        # Validate guess is a number
        if guess is None or guess <= 0:
            emit('guess_submitted', {'success': False, 'message': 'Please enter a valid price'})
            return

        # Convert to string for database storage
        guess = str(guess)

        # Get user
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            emit('guess_submitted', {'success': False, 'message': 'User not found'})
            return

        # Check if user already submitted guess for this product
        existing_guess = PriceGuessUser.query.filter_by(
            user_id=user.id,
            product_id=product_id
        ).first()

        if existing_guess:
            emit('guess_submitted', {'success': False, 'message': 'You have already submitted a guess!'})
            return

        # Create new guess
        new_guess = PriceGuessUser(
            user_id=user.id,
            product_id=product_id,
            answer=guess
        )
        db.session.add(new_guess)
        db.session.commit()

        print(f"Price guess submitted by {user.username}: {guess} for product {product_id}")

        # Notify admin and display of new submission
        total_submissions = PriceGuessUser.query.filter_by(product_id=product_id).count()
        emit('price_guess_received', {
            'product_id': product_id,
            'username': user.username,
            'total_submissions': total_submissions
        }, broadcast=True, include_self=False)

        # Notify display to show in sidebar
        emit('player_price_guess', {
            'username': user.username,
            'guess': float(guess)
        }, broadcast=True)

        emit('guess_submitted', {'success': True, 'message': 'Guess submitted!'})

    except Exception as e:
        print(f"Error submitting price guess: {e}")
        import traceback
        traceback.print_exc()
        emit('guess_submitted', {'success': False, 'message': f'Error submitting guess: {str(e)}'})

@socketio.on('price_guesser_calculate_results')
def handle_price_guesser_calculate_results(data):
    """Admin calculates results and shows winners"""
    from models.game import PriceGuessUser, Product

    if 'username' not in session or session['username'] != 'admin':
        return

    try:
        product_id = int(data['product_id'])
        actual_price = float(data['actual_price'])

        # Get all guesses for this product
        guesses = PriceGuessUser.query.filter_by(product_id=product_id).all()

        if not guesses:
            emit('error', {'message': 'No guesses submitted'})
            return

        # Calculate differences and find closest
        results = []
        for guess in guesses:
            try:
                guess_value = float(guess.answer.replace(',', '.').replace('€', '').strip())
                difference = abs(guess_value - actual_price)
                results.append({
                    'user_id': guess.user_id,
                    'username': guess.user.username,
                    'guess': guess_value,
                    'difference': difference,
                    'formatted_guess': f"{guess_value:.2f}€"
                })
            except ValueError:
                print(f"Invalid guess format from user {guess.user_id}: {guess.answer}")
                continue

        # Sort by difference
        results.sort(key=lambda x: x['difference'])

        # Find all winners (those with minimum difference)
        if results:
            min_difference = results[0]['difference']
            winners = [r for r in results if r['difference'] == min_difference]

            # Award points to winners
            for winner in winners:
                user = User.query.filter_by(id=winner['user_id']).first()
                if user:
                    user.overall_score += 1
                    winner['new_score'] = user.overall_score

            db.session.commit()

            # Get product info
            product = Product.query.filter_by(id=product_id).first()

            # Broadcast results
            emit('price_guesser_results', {
                'product_id': product_id,
                'product_name': product.product_name if product else 'Unknown',
                'actual_price': actual_price,
                'formatted_actual_price': f"{actual_price:.2f}€",
                'results': results,
                'winners': winners
            }, broadcast=True)

            print(f"Price guesser results calculated: {len(winners)} winner(s)")

    except Exception as e:
        print(f"Error calculating price guesser results: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': 'Error calculating results'})

# Spotify control functions
def handle_spotify_control(action, track_id):
    """Handle Spotify playback control on the server"""
    global current_spotify_track_id

    try:
        client = get_spotify_client()
        if not client:
            print("Spotify not authenticated")
            raise Exception("Spotify not authenticated. Please authenticate in admin panel.")

        if action == 'play':
            # Check if we're resuming the same track or starting a new one
            if current_spotify_track_id == track_id:
                # Same track - resume from current position
                try:
                    client.start_playback()
                    print(f"Resuming Spotify track: {track_id}")
                except spotipy.exceptions.SpotifyException as e:
                    if e.http_status == 404:
                        # No active device - try to activate one and start the track
                        devices = client.devices()
                        if devices['devices']:
                            device_id = devices['devices'][0]['id']
                            track_uri = f"spotify:track:{track_id}"
                            print(f"Trying to activate device and resume: {device_id}")
                            client.start_playback(device_id=device_id, uris=[track_uri])
                            print(f"Resumed Spotify track on device: {track_id}")
                        else:
                            raise
                    else:
                        raise
            else:
                # Different track - start from beginning
                track_uri = f"spotify:track:{track_id}"
                try:
                    client.start_playback(uris=[track_uri])
                    print(f"Started playing new Spotify track: {track_id}")
                    current_spotify_track_id = track_id  # Update currently playing track
                except spotipy.exceptions.SpotifyException as e:
                    if e.http_status == 404:
                        # Try to find and activate a device
                        devices = client.devices()
                        if devices['devices']:
                            device_id = devices['devices'][0]['id']
                            print(f"Trying to activate device: {device_id}")
                            client.start_playback(device_id=device_id, uris=[track_uri])
                            print(f"Started playing Spotify track on device: {track_id}")
                            current_spotify_track_id = track_id  # Update currently playing track
                        else:
                            raise
                    else:
                        raise

        elif action == 'pause':
            # Pause current playback (keep track ID to allow resume)
            client.pause_playback()
            print(f"Paused Spotify playback (track {current_spotify_track_id} can be resumed)")

        elif action == 'stop':
            # Stop playback and clear the current track (next play will start from beginning)
            client.pause_playback()
            current_spotify_track_id = None
            print("Stopped Spotify playback (track cleared)")
            
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 404:
            print("No active Spotify device found. User needs to start Spotify on a device.")
            raise Exception("No active Spotify device. Please start Spotify on your phone/computer.")
        else:
            print(f"Spotify API error: {e}")
            raise Exception(f"Spotify error: {e}")
    except Exception as e:
        print(f"Unexpected error controlling Spotify: {e}")
        raise

# Game-specific SocketIO events are handled by their respective game managers

# Game-specific SocketIO events are implemented in their respective game modules

if __name__ == '__main__':
    # Reset game state on server start
    with app.app_context():
        # Find existing game state or create new one
        game_state = GameState.query.first()
        if game_state:
            # Reset to inactive state
            game_state.is_active = False
            game_state.active_game = None
            db.session.commit()
            print("Game state reset to inactive on server start")
        else:
            # Create a new game state if none exists
            initial_state = GameState(is_active=False)
            db.session.add(initial_state)
            db.session.commit()
            print("New inactive game state created on server start")
    
    # Start the server
    print("\n" + "="*60)
    print("Starting server on port 5000...")
    print("Access the application at: http://192.168.178.75:5000")
    print("Spotify Web API control is fully supported over HTTP")
    print("="*60 + "\n")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
