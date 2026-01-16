from flask import session
from models.game import GameState
from models.user import User
from db import db
import json

class BaseGame:
    def __init__(self, socketio):
        self.socketio = socketio
        self.game_name = "base"
        self.is_active = False
    
    def initialize(self):
        """Initialize the game state"""
        self.is_active = True
        self.register_socket_events()
    
    def register_socket_events(self):
        """Register SocketIO event handlers specific to this game"""
        pass
    
    def update_game_state(self, data):
        """Update the game state in the database"""
        game_state = GameState.query.first()
        if game_state:
            current_data = json.loads(game_state.game_data) if game_state.game_data else {}
            current_data.update(data)
            game_state.game_data = json.dumps(current_data)
            db.session.commit()
    
    def get_game_state(self):
        """Get the game state from the database"""
        game_state = GameState.query.first()
        if game_state and game_state.game_data:
            return json.loads(game_state.game_data)
        return {}
    
    def update_player_score(self, username, game_type, score_change):
        """Update a player's score for a specific game"""
        user = User.query.filter_by(username=username).first()
        if user:
            if game_type == 'match_me':
                user.match_me_score += score_change
            elif game_type == 'geo_guessr':
                user.geo_guessr_score += score_change
            elif game_type == 'flappy_birds':
                user.flappy_birds_score += score_change
            elif game_type == 'buzzer':
                user.buzzer_score += score_change
            
            db.session.commit()
    
    def award_overall_point(self, username):
        """Award a point to the overall score for a player"""
        user = User.query.filter_by(username=username).first()
        if user:
            user.overall_score += 1
            db.session.commit()
    
    def end_game(self):
        """End the current game session"""
        self.is_active = False
        
        # Determine winner based on game-specific logic
        self.determine_winner()
    
    def determine_winner(self):
        """Determine the winner of the game and award points
        This method should be overridden by each game class"""
        pass
    
    def emit_to_display(self, event, data):
        """Send an event to the game display"""
        self.socketio.emit(event, data, broadcast=True)
    
    def emit_to_admin(self, event, data):
        """Send an event to the admin"""
        self.socketio.emit(event, data, room='admin')
    
    def emit_to_player(self, username, event, data):
        """Send an event to a specific player"""
        self.socketio.emit(event, data, room=username)
    
    def emit_to_all_players(self, event, data):
        """Send an event to all players"""
        self.socketio.emit(event, data, broadcast=True)
