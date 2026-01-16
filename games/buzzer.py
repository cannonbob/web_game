from games.base import BaseGame
from models.user import User
from db import db
from flask import session
import json

class BuzzerGame(BaseGame):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.game_name = "buzzer"
        self.buzzer_active = False
        self.current_buzzed_player = None
    
    def initialize(self):
        """Initialize the Buzzer game"""
        super().initialize()
        
        # Reset player scores for this game
        users = User.query.all()
        for user in users:
            user.buzzer_score = 0
        db.session.commit()
        
        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'buzzer_active': False,
            'current_buzzed_player': None,
            'player_scores': {}
        })
        
        # Notify players and display
        self.emit_to_all_players('buzzer_ready', {})
        self.emit_to_display('buzzer_init', {
            'users': [user.to_dict() for user in users if user.username != 'admin']
        })
    
    def register_socket_events(self):
        """Register SocketIO events for Buzzer game"""
        @self.socketio.on('buzzer_start')
        def handle_start(data):
            if session.get('username') == 'admin':
                self.start_buzzer()
        
        @self.socketio.on('buzzer_reset')
        def handle_reset(data):
            if session.get('username') == 'admin':
                self.reset_buzzer()
        
        @self.socketio.on('buzzer_correct')
        def handle_correct(data):
            if session.get('username') == 'admin':
                self.mark_answer_correct()
        
        @self.socketio.on('buzzer_wrong')
        def handle_wrong(data):
            if session.get('username') == 'admin':
                self.mark_answer_wrong()
        
        @self.socketio.on('buzzer_stop')
        def handle_stop(data):
            if session.get('username') == 'admin':
                self.end_game()
        
        @self.socketio.on('buzzer_buzz')
        def handle_buzz(data):
            if session.get('username') != 'admin' and self.is_active:
                username = session.get('username')
                self.player_buzz(username)
    
    def start_buzzer(self):
        """Start the Buzzer game"""
        self.is_active = True
        self.buzzer_active = True
        self.current_buzzed_player = None
        
        self.update_game_state({
            'status': 'active',
            'buzzer_active': True,
            'current_buzzed_player': None
        })
        
        # Notify players and display
        self.emit_to_all_players('buzzer_started', {})
        self.emit_to_display('buzzer_started', {
            'message': 'Buzzer is active. No one has buzzed yet.'
        })
    
    def reset_buzzer(self):
        """Reset the buzzer after a player has buzzed"""
        self.buzzer_active = True
        self.current_buzzed_player = None
        
        self.update_game_state({
            'buzzer_active': True,
            'current_buzzed_player': None
        })
        
        # Notify players and display
        self.emit_to_all_players('buzzer_reset', {})
        self.emit_to_display('buzzer_reset', {
            'message': 'Buzzer has been reset. No one has buzzed yet.'
        })
    
    def player_buzz(self, username):
        """Handle a player buzzing in"""
        game_state = self.get_game_state()
        
        # Only accept buzzes if buzzer is active and no one has buzzed yet
        if not game_state.get('buzzer_active', False) or game_state.get('current_buzzed_player'):
            return
        
        # Record the buzz
        self.buzzer_active = False
        self.current_buzzed_player = username
        
        self.update_game_state({
            'buzzer_active': False,
            'current_buzzed_player': username
        })
        
        # Notify players and display
        self.emit_to_all_players('buzzer_buzzed', {
            'username': username
        })
        
        self.emit_to_display('buzzer_buzzed', {
            'username': username,
            'message': f'{username} buzzed first!'
        })
        
        # Notify admin
        self.emit_to_admin('buzzer_player_buzzed', {
            'username': username
        })
    
    def mark_answer_correct(self):
        """Mark the current buzzed player's answer as correct"""
        game_state = self.get_game_state()
        username = game_state.get('current_buzzed_player')
        
        if not username:
            return
        
        # Update player score
        user = User.query.filter_by(username=username).first()
        if user:
            user.buzzer_score += 1
            db.session.commit()
        
        # Update player scores in game state
        player_scores = game_state.get('player_scores', {})
        player_scores[username] = player_scores.get(username, 0) + 1
        
        self.update_game_state({
            'player_scores': player_scores
        })
        
        # Notify players and display
        self.emit_to_all_players('buzzer_answer_correct', {
            'username': username,
            'scores': player_scores
        })
        
        self.emit_to_display('buzzer_answer_correct', {
            'username': username,
            'message': f'{username} answered correctly!',
            'scores': player_scores
        })
    
    def mark_answer_wrong(self):
        """Mark the current buzzed player's answer as wrong"""
        game_state = self.get_game_state()
        username = game_state.get('current_buzzed_player')
        
        if not username:
            return
        
        # Update player score
        user = User.query.filter_by(username=username).first()
        if user:
            user.buzzer_score -= 1
            db.session.commit()
        
        # Update player scores in game state
        player_scores = game_state.get('player_scores', {})
        player_scores[username] = max(0, player_scores.get(username, 0) - 1)
        
        self.update_game_state({
            'player_scores': player_scores
        })
        
        # Notify players and display
        self.emit_to_all_players('buzzer_answer_wrong', {
            'username': username,
            'scores': player_scores
        })
        
        self.emit_to_display('buzzer_answer_wrong', {
            'username': username,
            'message': f'{username} answered incorrectly!',
            'scores': player_scores
        })
    
    def determine_winner(self):
        """Determine the winner of the Buzzer game"""
        game_state = self.get_game_state()
        player_scores = game_state.get('player_scores', {})
        
        if not player_scores:
            return
        
        # Find player with highest score
        winner = max(player_scores.items(), key=lambda x: x[1], default=(None, 0))
        
        if winner[0]:
            # Award overall point to winner
            self.award_overall_point(winner[0])
        
        # Notify all players and display
        self.emit_to_all_players('buzzer_game_over', {
            'winner': winner[0],
            'scores': player_scores
        })
        
        self.emit_to_display('buzzer_game_over', {
            'winner': winner[0],
            'scores': player_scores
        })
