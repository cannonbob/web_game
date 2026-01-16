from games.base import BaseGame
from models.game import MatchMeCategory, MatchMeItem
from models.user import User
from db import db
from flask import session
import random
import json

class MatchMeGame(BaseGame):
    def __init__(self, socketio, category_id=None, question_text=None):
        super().__init__(socketio)
        self.game_name = "match_me"
        self.questions_per_player = 12
        self.category_id = category_id  # Category ID from question
        self.question_text = question_text  # Question text to display
        self.items = []  # Will be loaded from database

        # Load items if category_id is provided
        if self.category_id:
            self.load_items()

    def load_items(self):
        """Load items from database for this category"""
        if not self.category_id:
            print("ERROR: No category_id provided for match_me game")
            return

        # Load items and convert to dictionaries to avoid DetachedInstanceError
        items_query = MatchMeItem.query.filter_by(category_id=self.category_id).all()
        self.items = [item.to_dict() for item in items_query]
        print(f"Loaded {len(self.items)} items for match_me category {self.category_id}")

        if not self.items:
            print(f"WARNING: No items found for category {self.category_id}")

    def initialize(self):
        """Initialize the Match Me game"""
        super().initialize()
        
        # Reset player scores for this game
        users = User.query.all()
        for user in users:
            user.match_me_score = 0
        db.session.commit()
        
        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'used_titles': [],
            'used_artists': [],
            'used_answers': [],
            'used_questions': [],
            'player_states': {}
        })
        
        # Prepare initial player states
        for user in users:
            if user.username != 'admin':
                player_state = {
                    'current_question': 0,
                    'correct_answers': 0,
                    'completed': False,
                    'current_question_data': None,
                    'points': 0
                }
                self.update_player_state(user.username, player_state)
        
        # Notify players and display
        self.emit_to_all_players('match_me_ready', {})
        self.emit_to_display('match_me_init', {
            'users': [user.to_dict() for user in users if user.username != 'admin'],
            'question_text': self.question_text
        })

        # Game is initialized but not started - wait for admin to click "Start Game"
    
    def register_socket_events(self):
        """Register SocketIO events for Match Me game"""
        @self.socketio.on('match_me_start')
        def handle_start(data):
            if session.get('username') == 'admin':
                self.start_game()

        @self.socketio.on('match_me_answer')
        def handle_answer(data):
            if session.get('username') != 'admin' and self.is_active:
                username = session.get('username')
                title_id = data.get('title_id')
                artist_id = data.get('artist_id')
                self.process_answer(username, title_id, artist_id)

        @self.socketio.on('match_me_request_state')
        def handle_request_state(data):
            """Send current game state to requesting client (display)"""
            print("Match Me: Display state requested, sending game data")
            users = User.query.filter(User.username != 'admin').all()
            self.socketio.emit('match_me_init', {
                'users': [user.to_dict() for user in users],
                'question_text': self.question_text
            })
    
    def start_game(self):
        """Start the Match Me game"""
        self.is_active = True
        self.update_game_state({'status': 'active'})
        
        # Send countdown to all players
        self.emit_to_all_players('match_me_countdown', {'countdown': 3})
        self.emit_to_display('match_me_countdown', {'countdown': 3})
        
        # For each player, prepare their first question
        users = User.query.filter(User.username != 'admin').all()
        for user in users:
            question = self.generate_question(user.username)
            self.emit_to_player(user.username, 'match_me_question', question)
    
    def generate_question(self, username):
        """Generate a question for a player"""
        # Use items loaded from database
        if not self.items:
            print("ERROR: No items available for match_me game")
            return None

        # Filter out used titles
        game_state = self.get_game_state()
        used_titles = game_state.get('used_titles', [])
        available_items = [item for item in self.items if item['id'] not in used_titles]

        if not available_items:
            # If no more items, reset the used list
            used_titles = []
            self.update_game_state({'used_titles': []})
            available_items = self.items

        # Select one random item
        correct_item = random.choice(available_items)

        # Add to used titles
        used_titles.append(correct_item['id'])
        self.update_game_state({'used_titles': used_titles})

        # Get all answers from items (answer_text field)
        answers = list(set([item['answer_text'] for item in self.items]))

        # Filter out the correct answer and any used answers
        used_answers = game_state.get('used_answers', [])
        available_answers = [answer for answer in answers if answer != correct_item['answer_text'] and answer not in used_answers]

        if len(available_answers) < 4:
            # If not enough answers, reset the used list
            used_answers = []
            self.update_game_state({'used_answers': []})
            available_answers = [answer for answer in answers if answer != correct_item['answer_text']]

        # Select 4 random wrong answers
        wrong_answers = random.sample(available_answers, min(4, len(available_answers)))

        # Add to used answers
        used_answers.extend(wrong_answers)
        self.update_game_state({'used_answers': used_answers})

        # Combine correct and wrong answers
        all_answers = [correct_item['answer_text']] + wrong_answers
        random.shuffle(all_answers)

        # Create artists array with IDs AFTER shuffle
        all_artists = [{'id': i, 'name': answer} for i, answer in enumerate(all_answers)]

        # Find the correct artist ID after shuffle
        correct_artist_id = next(i for i, answer in enumerate(all_answers) if answer == correct_item['answer_text'])

        # Create the question
        question = {
            'title_id': correct_item['id'],
            'title': correct_item['question_text'],
            'correct_artist_id': correct_artist_id,
            'artists': all_artists
        }

        # Store this question in the player's state so we can retrieve it later
        player_state = self.get_player_state(username)
        player_state['current_question_data'] = question
        self.update_player_state(username, player_state)

        return question

    def generate_next_question(self, username, current_question, selected_artist_id, is_correct):
        """Generate next question by selectively replacing answers based on correctness"""
        from db import db

        # Extract current answers from the question
        current_answers = [artist['name'] for artist in current_question['artists']]

        # Get selected and correct answer names
        selected_answer = current_question['artists'][selected_artist_id]['name']
        correct_answer = current_question['artists'][current_question['correct_artist_id']]['name']

        # Get game state for tracking used items
        game_state = self.get_game_state()
        used_answers = game_state.get('used_answers', [])
        used_questions = game_state.get('used_questions', [])

        # Determine how many new answers we need
        if not is_correct:
            # Replace both selected and correct answers
            new_answers_needed = 2
        else:
            # Only replace selected answer
            new_answers_needed = 1

        # Build tuples for SQL NOT IN clauses
        used_answers_tuple = tuple(used_answers) if used_answers else ('',)
        current_answers_tuple = tuple(current_answers) if current_answers else ('',)
        used_questions_tuple = tuple(used_questions) if used_questions else ('',)

        # Get new answers that haven't been used and aren't in current answers
        new_answers_query = db.session.query(MatchMeItem.answer_text).distinct().filter(
            MatchMeItem.category_id == self.category_id,
            ~MatchMeItem.answer_text.in_(used_answers_tuple),
            ~MatchMeItem.answer_text.in_(current_answers_tuple)
        ).filter(
            MatchMeItem.answer_text.in_(
                db.session.query(MatchMeItem.answer_text).filter(
                    MatchMeItem.category_id == self.category_id,
                    ~MatchMeItem.question_text.in_(used_questions_tuple)
                )
            )
        ).order_by(db.func.random()).limit(new_answers_needed)

        new_answers_result = new_answers_query.all()

        if len(new_answers_result) < new_answers_needed:
            # Not enough new answers, end game
            return None

        new_answers = [row[0] for row in new_answers_result]

        # Update answers list
        updated_answers = current_answers.copy()

        if not is_correct:
            # Replace both selected and correct answers
            if selected_answer in updated_answers:
                selected_index = updated_answers.index(selected_answer)
                updated_answers[selected_index] = new_answers[0]
            if correct_answer in updated_answers:
                correct_index = updated_answers.index(correct_answer)
                # Avoid replacing same position twice
                if correct_index != updated_answers.index(new_answers[0]):
                    updated_answers[correct_index] = new_answers[1] if len(new_answers) > 1 else new_answers[0]
        else:
            # Replace only selected answer
            if selected_answer in updated_answers:
                selected_index = updated_answers.index(selected_answer)
                updated_answers[selected_index] = new_answers[0]

        # Ensure all answers are unique
        if len(set(updated_answers)) != len(updated_answers):
            return None

        # Choose new correct answer from updated list
        new_correct_answer = random.choice(updated_answers)

        # Get new question for the correct answer that hasn't been used
        question_query = db.session.query(MatchMeItem.question_text).filter(
            MatchMeItem.category_id == self.category_id,
            MatchMeItem.answer_text == new_correct_answer,
            ~MatchMeItem.question_text.in_(used_questions_tuple)
        ).order_by(db.func.random()).first()

        if not question_query:
            return None

        new_question = question_query[0]

        # Update used lists in game state
        used_questions.append(new_question)
        used_answers.extend(new_answers)
        self.update_game_state({
            'used_questions': used_questions,
            'used_answers': used_answers
        })

        # Create artists array with id and name (keep positions intact - no shuffle)
        artists = [{'id': i, 'name': answer} for i, answer in enumerate(updated_answers)]

        # Find the correct artist ID
        correct_artist_id = next(i for i, artist in enumerate(artists) if artist['name'] == new_correct_answer)

        # Create the question
        question = {
            'title_id': current_question.get('title_id', 0) + 1,
            'title': new_question,
            'correct_artist_id': correct_artist_id,
            'artists': artists
        }

        # Store this question in the player's state
        player_state = self.get_player_state(username)
        player_state['current_question_data'] = question
        self.update_player_state(username, player_state)

        return question
    
    def process_answer(self, username, title_id, selected_artist_id):
        """Process a player's answer"""
        print(f"DEBUG: process_answer called for {username}, title_id: {title_id}, selected_artist_id: {selected_artist_id}")
        
        # Get current player state
        player_state = self.get_player_state(username)
        print(f"DEBUG: Player state before: {player_state}")
        
        # Get the current question from player state
        question = player_state.get('current_question_data')
        
        if not question:
            print(f"DEBUG: No current question data found for {username}")
            return
        
        # Ensure selected_artist_id is an integer for comparison
        try:
            selected_artist_id = int(selected_artist_id)
        except (ValueError, TypeError):
            print(f"DEBUG: Invalid selected_artist_id: {selected_artist_id}")
            return
        
        # Check if the answer is correct
        correct_id = question.get('correct_artist_id')
        print(f"DEBUG: Selected artist ID: {selected_artist_id} (type: {type(selected_artist_id)})")
        print(f"DEBUG: Correct artist ID: {correct_id} (type: {type(correct_id)})")
        print(f"DEBUG: Question data: {question}")
        
        is_correct = selected_artist_id == correct_id
        print(f"DEBUG: Is answer correct? {is_correct}")
        
        # Update player state and scoring
        player_state['current_question'] += 1
        
        # Initialize points if not exists
        if 'points' not in player_state:
            player_state['points'] = 0
        
        points_change = 0
        if is_correct:
            player_state['correct_answers'] += 1
            player_state['points'] += 10  # 10 points for correct answer
            points_change = 10
            self.update_player_score(username, 'match_me', 10)
            print(f"DEBUG: Correct answer! Added 10 points. Total points: {player_state['points']}")
        else:
            # -5 points for wrong answer, but don't go below 0
            points_deduction = min(5, player_state['points'])  # Only deduct what we have, max 5
            player_state['points'] -= points_deduction
            points_change = -points_deduction
            self.update_player_score(username, 'match_me', -points_deduction)
            print(f"DEBUG: Wrong answer! Deducted {points_deduction} points. Total points: {player_state['points']}")
        
        print(f"DEBUG: Player state after: {player_state}")
        
        # Check if player has completed all questions
        if player_state['current_question'] >= self.questions_per_player:
            player_state['completed'] = True
            self.update_player_state(username, player_state)
            
            # Send final answer result first (so they see the score change for last question)
            self.emit_to_player(username, 'match_me_answer_result', {
                'is_correct': is_correct,
                'correct_artist_id': correct_id,
                'points_change': points_change,
                'progress': {
                    'current': player_state['current_question'],
                    'total': self.questions_per_player,
                    'correct': player_state['correct_answers'],
                    'points': player_state.get('points', 0)
                }
            })
            
            # Notify player of completion
            completion_data = {
                'correct_answers': player_state['correct_answers'],
                'total_questions': self.questions_per_player,
                'points': player_state.get('points', 0)
            }
            print(f"Sending match_me_completed to {username}: {completion_data}")
            self.emit_to_player(username, 'match_me_completed', completion_data)
            
            # End the game immediately when first player finishes
            print(f"Player {username} finished - ending game for all players")
            self.end_game_for_all_players()
        else:
            # Update player state
            self.update_player_state(username, player_state)

            # Generate next question with selective answer replacement
            next_question = self.generate_next_question(username, question, selected_artist_id, is_correct)

            if next_question:
                self.emit_to_player(username, 'match_me_question', next_question)

                # Notify about answer result
                self.emit_to_player(username, 'match_me_answer_result', {
                    'is_correct': is_correct,
                    'correct_artist_id': correct_id,
                    'points_change': points_change,
                    'progress': {
                        'current': player_state['current_question'],
                        'total': self.questions_per_player,
                        'correct': player_state['correct_answers'],
                        'points': player_state.get('points', 0)
                    }
                })
            else:
                # Couldn't generate next question (ran out of answers/questions), end game early
                print(f"Could not generate next question for {username}, ending game early")
                player_state['completed'] = True
                self.update_player_state(username, player_state)

                # Send completion notification
                completion_data = {
                    'correct_answers': player_state['correct_answers'],
                    'total_questions': self.questions_per_player,
                    'points': player_state.get('points', 0),
                    'game_ended_early': True
                }
                self.emit_to_player(username, 'match_me_completed', completion_data)

                # Check if all players are done
                if self.all_players_completed():
                    self.end_game()
    
    def get_question_by_title_id(self, title_id):
        """Get a question by title ID - retrieve from current player state"""
        # We can't reliably reconstruct the question from just the title_id
        # because the artist IDs depend on the shuffled order
        # Instead, we need to get it from the current player state
        return None
    
    def update_player_state(self, username, state):
        """Update a player's state in the game state"""
        game_state = self.get_game_state()
        player_states = game_state.get('player_states', {})
        player_states[username] = state
        self.update_game_state({'player_states': player_states})
    
    def get_player_state(self, username):
        """Get a player's state from the game state"""
        game_state = self.get_game_state()
        player_states = game_state.get('player_states', {})
        return player_states.get(username, {
            'current_question': 0,
            'correct_answers': 0,
            'completed': False,
            'current_question_data': None,
            'points': 0
        })
    
    def all_players_completed(self):
        """Check if all players have completed the game"""
        game_state = self.get_game_state()
        player_states = game_state.get('player_states', {})
        
        for username, state in player_states.items():
            if not state.get('completed', False) and username != 'admin':
                return False
        
        return True
    
    def notify_progress(self, completed_username):
        """Notify all players about someone's completion"""
        self.emit_to_all_players('match_me_player_completed', {
            'username': completed_username,
            'remaining_players': self.get_remaining_players()
        })
        
        self.emit_to_display('match_me_player_completed', {
            'username': completed_username,
            'remaining_players': self.get_remaining_players()
        })
    
    def get_remaining_players(self):
        """Get list of players who haven't completed the game"""
        game_state = self.get_game_state()
        player_states = game_state.get('player_states', {})
        
        remaining = []
        for username, state in player_states.items():
            if not state.get('completed', False) and username != 'admin':
                remaining.append(username)
        
        return remaining
    
    def end_game_for_all_players(self):
        """End the game for all players when the first player finishes"""
        # Mark all players as completed
        game_state = self.get_game_state()
        player_states = game_state.get('player_states', {})
        
        # Notify all remaining players that the game has ended
        for username, state in player_states.items():
            if not state.get('completed', False):
                # Mark as completed
                state['completed'] = True
                self.update_player_state(username, state)
                
                # Notify player of game completion
                completion_data = {
                    'correct_answers': state['correct_answers'],
                    'total_questions': self.questions_per_player,
                    'points': state.get('points', 0),
                    'game_ended_early': True
                }
                print(f"Sending match_me_completed to {username} (game ended early): {completion_data}")
                self.emit_to_player(username, 'match_me_completed', completion_data)
        
        # End the actual game
        self.end_game()

    def end_game(self):
        """End the Match Me game"""
        print("Match Me: end_game called")
        
        # Update game state
        self.update_game_state({'status': 'ended'})
        
        # Call parent class end_game
        super().end_game()

    def determine_winner(self):
        """Determine the winner of the Match Me game based on points"""
        game_state = self.get_game_state()

        # Check if winner was already determined (prevent duplicate point awards)
        if game_state.get('winner_determined', False):
            print("Match Me: Winner already determined, skipping point award")
            return

        users = User.query.filter(User.username != 'admin').all()
        player_states = game_state.get('player_states', {})

        # Create scores dictionary with points from player states
        scores = {}
        for user in users:
            player_state = player_states.get(user.username, {})
            scores[user.username] = player_state.get('points', 0)

        # Find user with highest points
        if scores:
            winner_username = max(scores, key=scores.get)
            winner_points = scores[winner_username]

            # Award 1 overall point to winner only
            winner_user = User.query.filter_by(username=winner_username).first()
            if winner_user:
                old_overall_score = winner_user.overall_score
                winner_user.overall_score += 1
                db.session.commit()
                print(f"Match Me: Awarded 1 overall point to {winner_username} (was {old_overall_score}, now {winner_user.overall_score})")

            # Mark winner as determined
            self.update_game_state({'winner_determined': True})

            print(f"Winner: {winner_username} with {winner_points} match_me points")
            print(f"All scores: {scores}")

            # Notify all players and display
            self.emit_to_all_players('match_me_game_over', {
                'winner': winner_username,
                'scores': scores,
                'winner_points': winner_points
            })

            self.emit_to_display('match_me_game_over', {
                'winner': winner_username,
                'scores': scores,
                'winner_points': winner_points
            })
        else:
            print("No players found for winner determination")
