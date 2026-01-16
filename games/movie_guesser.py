from games.base import BaseGame
from models.game import Movie, AnswerUser
from models.user import User
from db import db
from flask import session, request
from rapidfuzz import fuzz

class MovieGuessrGame(BaseGame):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.game_name = "movie_guesser"

    def initialize(self):
        """Initialize the Movie Guesser game"""
        super().initialize()

        # Register socket events
        self.register_socket_events()

        # Reset player scores for this game
        users = User.query.all()
        for user in users:
            if hasattr(user, 'movie_guesser_score'):
                user.movie_guesser_score = 0
        db.session.commit()

        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'current_screenshot': None,
            'player_guesses': {}
        })

        # Don't redirect here - routing is handled by question selection in app.py
        print("Movie guesser initialized and handlers registered")

    def register_socket_events(self):
        """Register SocketIO events for Movie Guesser game"""

        @self.socketio.on('search_movies')
        def handle_search_movies(data):
            """Handle movie search requests with fuzzy matching"""
            query = data.get('query', '').strip()

            if not query or len(query) < 2:
                self.socketio.emit('movie_search_results', [], room=request.sid)
                return

            # Get all movies from database
            all_movies = Movie.query.all()

            query_lower = query.lower()
            results = []

            for movie in all_movies:
                title_lower = movie.title.lower()

                # Calculate fuzzy match score
                fuzzy_score = fuzz.partial_ratio(query_lower, title_lower)

                # Check if movie title starts with query (prioritize these)
                starts_with = title_lower.startswith(query_lower)

                # Only include movies with reasonable match (60%+ fuzzy score)
                if fuzzy_score >= 60:
                    results.append({
                        'id': movie.id,
                        'title': movie.title,
                        'year': movie.year,
                        'display': f"{movie.title} ({movie.year})",
                        'fuzzy_score': fuzzy_score,
                        'starts_with': starts_with
                    })

            # Sort results: prioritize starts_with, then by fuzzy_score
            results.sort(key=lambda x: (not x['starts_with'], -x['fuzzy_score']))

            # Return max 10 results to the requesting client only
            self.socketio.emit('movie_search_results', results[:10], room=request.sid)

        @self.socketio.on('check_player_guessed')
        def handle_check_player_guessed(data):
            """Check if a player has already guessed for the current question"""
            if session.get('username') == 'admin':
                return

            username = session.get('username')
            question_id = data.get('question_id')

            # Check if player already has a guess for this question
            user = User.query.filter_by(username=username).first()
            if not user:
                return

            existing_guess = AnswerUser.query.filter_by(
                user_id=user.id,
                question_id=question_id
            ).first()

            has_guessed = existing_guess is not None

            self.socketio.emit('player_guess_status', {
                'has_guessed': has_guessed,
                'question_id': question_id
            }, room=request.sid)

    def determine_winner(self):
        """Determine the winner of the Movie Guesser game"""
        # This will be called when the game ends
        # Scoring is handled by the existing input question system
        pass
