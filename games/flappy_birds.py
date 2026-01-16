from games.base import BaseGame
from models.user import User
from db import db
from flask import session
import json

class FlappyBirdsGame(BaseGame):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.game_name = "flappy_birds"
    
    def initialize(self):
        """Initialize the Flappy Birds game"""
        super().initialize()
        
        # Reset player scores for this game
        users = User.query.all()
        for user in users:
            user.flappy_birds_score = 0
        db.session.commit()
        
        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'player_scores': {}
        })
        
        # Notify players and display
        self.emit_to_all_players('flappy_birds_ready', {})
        self.emit_to_display('flappy_birds_init', {
            'users': [user.to_dict() for user in users if user.username != 'admin']
        })
    
    def register_socket_events(self):
        """Register SocketIO events for Flappy Birds game"""
        @self.socketio.on('flappy_birds_start')
        def handle_start(data):
            if session.get('username') == 'admin':
                self.start_game()
        
        @self.socketio.on('flappy_birds_end')
        def handle_end(data):
            if session.get('username') == 'admin':
                self.end_game()
        
        @self.socketio.on('flappy_birds_submit_score')
        def handle_submit_score(data):
            if session.get('username') != 'admin' and self.is_active:
                username = session.get('username')
                score = data.get('score', 0)
                self.submit_score(username, score)
    
    def start_game(self):
        """Start the Flappy Birds game"""
        self.is_active = True
        self.update_game_state({
            'status': 'active',
            'player_scores': {}
        })
        
        # Notify players and display
        self.emit_to_all_players('flappy_birds_started', {})
        self.emit_to_display('flappy_birds_started', {})
    
    def submit_score(self, username, score):
        """Submit a score for a player"""
        print(f"FLAPPY DEBUG: submit_score called - username={username}, score={score}")
        game_state = self.get_game_state()
        player_scores = game_state.get('player_scores', {})
        print(f"FLAPPY DEBUG: Current player_scores: {player_scores}")

        # Only update if the score is higher than previous
        if username not in player_scores or score > player_scores[username]:
            player_scores[username] = score
            self.update_game_state({'player_scores': player_scores})
            print(f"FLAPPY DEBUG: Updated player_scores to: {player_scores}")

            # Update the display with live scores
            self.emit_to_display('flappy_birds_update_scores', {
                'username': username,
                'score': score,
                'scores': player_scores
            })
        else:
            print(f"FLAPPY DEBUG: Score {score} not higher than existing {player_scores.get(username, 0)}")
    
    def determine_winner(self):
        """Determine the winner of the Flappy Birds game"""
        print("FLAPPY DEBUG: determine_winner called")
        game_state = self.get_game_state()
        player_scores = game_state.get('player_scores', {})
        print(f"FLAPPY DEBUG: Retrieved player_scores from game_state: {player_scores}")

        winner_username = None

        if player_scores:
            # Find player with highest score
            winner = max(player_scores.items(), key=lambda x: x[1])
            winner_username = winner[0]
            print(f"FLAPPY DEBUG: Winner determined: {winner_username} with score {winner[1]}")

            # Update database scores
            for username, score in player_scores.items():
                user = User.query.filter_by(username=username).first()
                if user:
                    print(f"FLAPPY DEBUG: Setting {username}.flappy_birds_score = {score}")
                    user.flappy_birds_score = score
                else:
                    print(f"FLAPPY DEBUG: User {username} not found in database!")

            # Award overall point to winner
            print(f"FLAPPY DEBUG: Awarding overall point to {winner_username}")
            self.award_overall_point(winner_username)

            db.session.commit()
            print("FLAPPY DEBUG: Database changes committed")
        else:
            print("FLAPPY DEBUG: No player_scores found!")

        # Always notify players and display, even if no scores
        game_over_data = {
            'winner': winner_username if winner_username else 'No one played',
            'scores': player_scores
        }
        print(f"FLAPPY DEBUG: Emitting game_over_data: {game_over_data}")

        self.emit_to_all_players('flappy_birds_game_over', game_over_data)
        self.emit_to_display('flappy_birds_game_over', game_over_data)
