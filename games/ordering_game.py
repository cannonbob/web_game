from games.base import BaseGame
from models.game import OrderItem, Question
from models.user import User
from db import db
from flask import session, request
import json

class OrderingGame(BaseGame):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.game_name = "ordering_game"

    def initialize(self):
        """Initialize the Ordering game"""
        super().initialize()

        # Register socket events
        self.register_socket_events()

        # Reset player scores for this game
        users = User.query.all()
        for user in users:
            if hasattr(user, 'ordering_score'):
                user.ordering_score = 0
        db.session.commit()

        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'current_question': None,
            'player_submissions': {},  # {username: {order: [...], score: float}}
            'correct_order': []
        })

        print("Ordering game initialized and handlers registered")

    def register_socket_events(self):
        """Register SocketIO events for Ordering game"""

        @self.socketio.on('submit_order')
        def handle_submit_order(data):
            """Handle player's submitted order"""
            if session.get('username') == 'admin':
                return

            username = session.get('username')
            question_id = data.get('question_id')
            submitted_order = data.get('order', [])  # List of item names in player's order

            if not username or not question_id or not submitted_order:
                return

            # Get the question and its order items
            question = Question.query.get(question_id)
            if not question:
                return

            order_items = OrderItem.query.filter_by(question_id=question_id).order_by(OrderItem.position).all()
            if not order_items:
                return

            # Calculate correctness score using Kendall Tau Distance
            score = self.calculate_kendall_tau_score(order_items, submitted_order)

            # Store the submission in game state
            game_state = self.get_game_state()
            if 'player_submissions' not in game_state:
                game_state['player_submissions'] = {}

            game_state['player_submissions'][username] = {
                'order': submitted_order,
                'score': score
            }
            self.update_game_state(game_state)

            # Notify the player that their submission was received
            self.socketio.emit('order_submitted', {
                'success': True,
                'message': 'Your order has been submitted!'
            }, room=request.sid)

            # Notify admin about the submission count
            submission_count = len(game_state['player_submissions'])
            total_players = User.query.filter(User.username != 'admin').count()
            self.socketio.emit('submission_update', {
                'count': submission_count,
                'total': total_players
            }, broadcast=True)

        @self.socketio.on('check_player_submitted')
        def handle_check_player_submitted(data):
            """Check if a player has already submitted their order"""
            if session.get('username') == 'admin':
                return

            username = session.get('username')
            question_id = data.get('question_id')

            game_state = self.get_game_state()
            player_submissions = game_state.get('player_submissions', {})
            has_submitted = username in player_submissions

            self.socketio.emit('player_submission_status', {
                'has_submitted': has_submitted,
                'question_id': question_id
            }, room=request.sid)

        @self.socketio.on('end_ordering_round')
        def handle_end_ordering_round(data):
            """Admin ends the round and reveals results"""
            if session.get('username') != 'admin':
                return

            question_id = data.get('question_id')
            if not question_id:
                return

            # Get the correct order
            order_items = OrderItem.query.filter_by(question_id=question_id).order_by(OrderItem.position).all()
            correct_order = [item.item_name for item in order_items]

            # Get all submissions and calculate winners
            game_state = self.get_game_state()
            player_submissions = game_state.get('player_submissions', {})

            # Find the highest score
            if player_submissions:
                max_score = max(sub['score'] for sub in player_submissions.values())
                winners = [username for username, sub in player_submissions.items() if sub['score'] == max_score]

                # Award points to all tied winners
                for winner in winners:
                    self.award_overall_point(winner)
            else:
                winners = []
                max_score = 0

            # Prepare results for display
            results = []
            for username, submission in player_submissions.items():
                user = User.query.filter_by(username=username).first()
                results.append({
                    'username': username,
                    'order': submission['order'],
                    'score': submission['score'],
                    'is_winner': username in winners,
                    'overall_score': user.overall_score if user else 0
                })

            # Sort results by score descending
            results.sort(key=lambda x: x['score'], reverse=True)

            # Emit results to all clients
            self.socketio.emit('ordering_results', {
                'correct_order': correct_order,
                'correct_items': [item.to_dict() for item in order_items],
                'results': results,
                'winners': winners
            }, broadcast=True)

    def calculate_kendall_tau_score(self, order_items, submitted_order):
        """
        Calculate Kendall Tau Distance-based score
        Returns a score between 0 and 1 (1 = perfect, 0 = worst possible)

        Kendall Tau counts the number of pairwise inversions between two orderings
        """
        # Create a mapping from item name to correct position
        correct_positions = {item.item_name: item.position for item in order_items}

        # Get the positions for the submitted order
        n = len(submitted_order)

        # Count inversions: pairs that are in wrong relative order
        inversions = 0
        for i in range(n):
            for j in range(i + 1, n):
                item_i = submitted_order[i]
                item_j = submitted_order[j]

                # Skip if items aren't in the correct set
                if item_i not in correct_positions or item_j not in correct_positions:
                    continue

                pos_i = correct_positions[item_i]
                pos_j = correct_positions[item_j]

                # If i should come after j but comes before, it's an inversion
                if pos_i > pos_j:
                    inversions += 1

        # Maximum possible inversions for n items is n*(n-1)/2
        max_inversions = n * (n - 1) / 2

        # Normalize to 0-1 score (1 is perfect)
        if max_inversions == 0:
            return 1.0

        score = 1.0 - (inversions / max_inversions)
        return round(score, 4)

    def determine_winner(self):
        """Determine the winner of the Ordering game"""
        # Winner determination is handled in end_ordering_round
        pass
