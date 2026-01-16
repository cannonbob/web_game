from games.base import BaseGame
from models.game import SortingCategory, SortingItem, Question
from models.user import User
from db import db
from flask import session
import random

class SortingGame(BaseGame):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.game_name = "sorting_game"
        self.question_id = None

    def initialize(self):
        """Initialize the This or That game"""
        print("SortingGame: initialize() called")
        super().initialize()

        # Get the current question (should be set when this game is started from a 'tt' question)
        # For now, we'll handle it when the game starts

        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'player_states': {},
            'game_ended': False,
            'winner': None
        })

        # Notify players and display
        print("SortingGame: Emitting sorting_game_ready to all players")
        self.emit_to_all_players('sorting_game_ready', {})

        print("SortingGame: Initialization complete")
        # Game is initialized but not started

    def register_socket_events(self):
        """Register SocketIO events for This or That game"""
        print("SortingGame: Registering socket events")

        @self.socketio.on('sorting_game_start')
        def handle_start(data):
            print(f"SortingGame: Received sorting_game_start event from {session.get('username')}")
            if session.get('username') == 'admin':
                question_id = data.get('question_id')
                if question_id:
                    print(f"SortingGame: Admin starting game with question_id={question_id}")
                    self.start_game(question_id)

        @self.socketio.on('sorting_game_submit_sort')
        def handle_submit_sort(data):
            if session.get('username') != 'admin' and self.is_active:
                username = session.get('username')
                item_id = data.get('item_id')
                category_id = data.get('category_id')
                self.process_sort(username, item_id, category_id)

        @self.socketio.on('sorting_game_get_items')
        def handle_get_items(data):
            """Send all items to a player when they request them"""
            if session.get('username') != 'admin' and self.is_active:
                username = session.get('username')
                self.send_items_to_player(username)

    def start_game(self, question_id):
        """Start the Sorting game with a specific question"""
        print(f"SortingGame: start_game() called with question_id={question_id}")

        # Check if game already started (prevent duplicate starts)
        game_state = self.get_game_state()
        if game_state.get('status') == 'active':
            print(f"SortingGame: Game already active, ignoring duplicate start")
            return

        self.question_id = question_id
        self.is_active = True
        self.update_game_state({'status': 'active', 'question_id': question_id})

        # Get the question and its categories/items
        question = Question.query.get(question_id)
        if not question:
            print(f"SortingGame ERROR: Question {question_id} not found")
            return

        categories = SortingCategory.query.filter_by(question_id=question_id).all()
        print(f"SortingGame: Found {len(categories)} categories")
        if len(categories) != 2:
            print(f"SortingGame ERROR: Question {question_id} does not have exactly 2 categories")
            return

        items = SortingItem.query.filter_by(question_id=question_id).all()
        print(f"SortingGame: Found {len(items)} items")
        if not items:
            print(f"SortingGame ERROR: Question {question_id} has no items")
            return

        # Prepare game data
        game_data = {
            'question': question.question_text,
            'categories': [cat.to_dict() for cat in categories],
            'items': [item.to_dict() for item in items],
            'total_items': len(items)
        }

        # Initialize player states
        users = User.query.filter(User.username != 'admin').all()
        for user in users:
            # Create random order of items for this player
            shuffled_items = items.copy()
            random.shuffle(shuffled_items)

            player_state = {
                'score': 0,
                'items_sorted': 0,
                'completed': False,
                'item_order': [item.id for item in shuffled_items],
                'current_item_index': 0
            }
            self.update_player_state(user.username, player_state)

        # Send countdown to all players
        print(f"SortingGame: Sending countdown to all players")
        self.emit_to_all_players('sorting_game_countdown', {'countdown': 3})

        # Send game data to all players
        print(f"SortingGame: Sending game data to {len(users)} players")
        for user in users:
            player_state = self.get_player_state(user.username)
            player_data = game_data.copy()
            # Don't send the full items list, player will request items one by one
            player_data['items'] = []
            player_data['total_items'] = len(items)

            print(f"SortingGame: Sending game_data to {user.username}")
            self.emit_to_player(user.username, 'sorting_game_data', player_data)

            # Send first item
            print(f"SortingGame: Sending first item to {user.username}")
            self.send_next_item(user.username)

    def send_items_to_player(self, username):
        """Send all items in random order to a player"""
        player_state = self.get_player_state(username)
        if not player_state:
            return

        item_order = player_state.get('item_order', [])
        items_data = []

        for item_id in item_order:
            item = SortingItem.query.get(item_id)
            if item:
                items_data.append(item.to_dict())

        self.emit_to_player(username, 'sorting_game_all_items', {'items': items_data})

    def send_next_item(self, username):
        """Send the next item to a player"""
        player_state = self.get_player_state(username)
        if not player_state:
            return

        current_index = player_state.get('current_item_index', 0)
        item_order = player_state.get('item_order', [])

        if current_index >= len(item_order):
            # Player has completed all items
            self.complete_player_game(username)
            return

        item_id = item_order[current_index]
        item = SortingItem.query.get(item_id)

        if not item:
            print(f"Item {item_id} not found")
            return

        self.emit_to_player(username, 'sorting_game_item', {
            'item': item.to_dict(),
            'progress': {
                'current': current_index + 1,
                'total': len(item_order)
            }
        })

    def process_sort(self, username, item_id, category_id):
        """Process a player's sort action"""
        if not self.is_active:
            return

        game_state = self.get_game_state()
        if game_state.get('game_ended'):
            return

        player_state = self.get_player_state(username)
        if not player_state or player_state.get('completed'):
            return

        # Get the item
        item = SortingItem.query.get(item_id)
        if not item:
            return

        # Check if correct
        is_correct = (item.category_id == category_id)

        # Update score
        score = player_state.get('score', 0)
        if is_correct:
            score += 10
        else:
            # Deduct 5 points but don't go below 0
            score = max(0, score - 5)

        items_sorted = player_state.get('items_sorted', 0) + 1

        player_state['score'] = score
        player_state['items_sorted'] = items_sorted
        player_state['current_item_index'] = items_sorted

        self.update_player_state(username, player_state)

        # Send feedback to player
        self.emit_to_player(username, 'sorting_game_result', {
            'correct': is_correct,
            'score': score,
            'items_sorted': items_sorted
        })

        # Send next item or complete game
        self.send_next_item(username)

    def complete_player_game(self, username):
        """Mark a player as completed and check if game should end"""
        player_state = self.get_player_state(username)
        if not player_state:
            return

        player_state['completed'] = True
        self.update_player_state(username, player_state)

        # Notify player they're done
        self.emit_to_player(username, 'sorting_game_player_completed', {
            'score': player_state.get('score', 0)
        })

        # End game for everyone (first player to finish ends the game)
        self.end_sorting_game()

    def end_sorting_game(self):
        """End the game and determine winner"""
        game_state = self.get_game_state()
        if game_state.get('game_ended'):
            return

        # Mark game as ended
        game_state['game_ended'] = True
        self.update_game_state(game_state)

        # Collect all player scores
        users = User.query.filter(User.username != 'admin').all()
        player_scores = []

        for user in users:
            player_state = self.get_player_state(user.username)
            if player_state:
                player_scores.append({
                    'username': user.username,
                    'score': player_state.get('score', 0),
                    'items_sorted': player_state.get('items_sorted', 0)
                })

        # Sort by score (descending)
        player_scores.sort(key=lambda x: x['score'], reverse=True)

        # Award 1 point to winner
        if player_scores:
            winner = player_scores[0]
            winner_user = User.query.filter_by(username=winner['username']).first()
            if winner_user:
                winner_user.overall_score = (winner_user.overall_score or 0) + 1
                db.session.commit()

        # Send results to all players
        self.emit_to_all_players('sorting_game_ended', {
            'results': player_scores
        })

        # Send results to display
        self.emit_to_display('sorting_game_results', {
            'results': player_scores
        })

        # End the game
        self.is_active = False

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
            'score': 0,
            'items_sorted': 0,
            'completed': False,
            'item_order': [],
            'current_item_index': 0
        })
