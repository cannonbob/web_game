from games.base import BaseGame
from models.user import User
from db import db
from flask import session
import os
import random


class CoopPuzzleGame(BaseGame):
    def __init__(self, socketio, media_url=None):
        super().__init__(socketio)
        self.game_name = "coop_puzzle"
        self.rows = 5
        self.cols = 5
        self.teams = {}  # {team_id: [usernames]}
        self.player_states = {}  # {username: {piece_id: {x, y, isLocked}}}
        self.current_image = None  # Path to the current puzzle image
        self.media_url = media_url  # Media URL from question (if question-based)

        # Testing mode: Set to True to put all players in one team
        self.test_mode_single_team = False

    def select_random_image(self):
        """Select a random puzzle image from the static/images/puzzle folder"""
        puzzle_folder = os.path.join('static', 'images', 'puzzle')

        # Get all image files from the folder
        if os.path.exists(puzzle_folder):
            image_files = [f for f in os.listdir(puzzle_folder)
                          if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

            if image_files:
                selected_image = random.choice(image_files)
                # Return the web path (relative to static folder)
                self.current_image = f'/static/images/puzzle/{selected_image}'
                print(f"CoopPuzzle: Selected image: {self.current_image}")
                return self.current_image

        # Fallback to a default if no images found
        print("CoopPuzzle: Warning - No images found in puzzle folder")
        return None

    def initialize(self):
        """Initialize the cooperative puzzle game"""
        super().initialize()

        # Reset player scores for this game
        users = User.query.filter(User.username != 'admin').all()
        for user in users:
            user.puzzle_score = 0
        db.session.commit()

        # Assign teams based on player count
        self.assign_teams(users)

        # Use media_url from question if provided, otherwise select random image
        if self.media_url:
            # Ensure path starts with / for absolute URL resolution
            if not self.media_url.startswith('/'):
                self.current_image = '/' + self.media_url
            else:
                self.current_image = self.media_url
            print(f"CoopPuzzle: Using question media_url: {self.current_image}")
        else:
            self.select_random_image()

        # Initialize game state
        self.update_game_state({
            'status': 'ready',
            'teams': self.teams,
            'player_states': self.player_states,
            'game_over': False,
            'winning_team': None,
            'image_path': self.current_image
        })

        # Notify players with their team assignments and image path
        self.emit_to_all_players('coop_puzzle_ready', {
            'teams': self.teams,
            'total_pieces': self.rows * self.cols,
            'image_path': self.current_image
        })

        # Notify display
        self.emit_to_display('coop_puzzle_init', {
            'teams': self.teams,
            'users': [user.to_dict() for user in users if user.username != 'admin'],
            'image_path': self.current_image
        })

        print(f"CoopPuzzle: Initialized with teams: {self.teams}")

    def assign_teams(self, users):
        """Assign players to teams based on player count"""
        import random

        usernames = [u.username for u in users if u.username != 'admin']
        # Randomize player order before assigning teams
        random.shuffle(usernames)
        player_count = len(usernames)

        print(f"CoopPuzzle: Assigning {player_count} players to teams (randomized)")

        # TEST MODE: All players in one team
        if self.test_mode_single_team:
            self.teams["team_1"] = usernames
            for username in usernames:
                self.player_states[username] = {}
            print(f"CoopPuzzle: TEST MODE - All {player_count} players in team_1")
            return

        # NORMAL MODE: Dynamic team assignment based on player count
        if player_count < 4:
            # Individual play - each player is their own team
            for i, username in enumerate(usernames):
                self.teams[f"team_{i+1}"] = [username]
                self.player_states[username] = {}
            print("CoopPuzzle: Individual play (< 4 players)")

        elif player_count == 4:
            # 2 teams of 2
            self.teams["team_1"] = usernames[:2]
            self.teams["team_2"] = usernames[2:4]
            for username in usernames:
                self.player_states[username] = {}
            print("CoopPuzzle: 2 teams of 2")

        else:
            # More than 4 players - divide into teams of ~3
            team_size = 3
            num_teams = (player_count + team_size - 1) // team_size  # Ceiling division

            # Distribute players evenly
            for i in range(num_teams):
                team_id = f"team {i+1}"
                start_idx = i * team_size
                end_idx = min(start_idx + team_size, player_count)
                self.teams[team_id] = usernames[start_idx:end_idx]

            for username in usernames:
                self.player_states[username] = {}

            print(f"CoopPuzzle: {num_teams} teams of ~{team_size}")

    def register_socket_events(self):
        """Register SocketIO events for Cooperative Puzzle game"""
        @self.socketio.on('coop_puzzle_start')
        def handle_start(data):
            if session.get('username') == 'admin':
                self.start_game()

        @self.socketio.on('coop_puzzle_update_piece')
        def handle_update_piece(data):
            username = session.get('username')
            if username and username != 'admin' and self.is_active:
                self.update_piece_position(username, data)

                # Only check completion and broadcast when piece is locked
                if data.get('isLocked', False):
                    self.broadcast_team_progress()
                    winning_team = self.check_team_completion()
                    if winning_team:
                        self.handle_game_completion(winning_team)

        @self.socketio.on('coop_puzzle_end')
        def handle_end(data):
            if session.get('username') == 'admin':
                self.end_game()

        @self.socketio.on('coop_puzzle_request_state')
        def handle_request_state(data):
            """Send current game state to requesting client (display)"""
            print("CoopPuzzle: Display state requested, sending teams data")
            self.socketio.emit('coop_puzzle_init', {
                'teams': self.teams,
                'total_pieces': self.rows * self.cols,
                'image_path': self.current_image
            })

        @self.socketio.on('coop_puzzle_request_ready')
        def handle_request_ready(data):
            """Send ready state to requesting player"""
            print("CoopPuzzle: Player state requested, sending ready data")
            self.socketio.emit('coop_puzzle_ready', {
                'teams': self.teams,
                'total_pieces': self.rows * self.cols,
                'image_path': self.current_image
            })

    def start_game(self):
        """Start the cooperative puzzle game"""
        print("CoopPuzzle: start_game() called")
        self.is_active = True

        # Update game state
        self.update_game_state({
            'status': 'active',
            'game_over': False
        })

        # Notify all players to start
        self.emit_to_all_players('coop_puzzle_started', {})

        # Notify display
        self.emit_to_display('coop_puzzle_started', {})

        print("CoopPuzzle: Game started")

    def update_piece_position(self, username, data):
        """Update a piece position for a player"""
        piece_id = data.get('piece_id')
        x = data.get('x')
        y = data.get('y')
        is_locked = data.get('isLocked', False)

        if username not in self.player_states:
            self.player_states[username] = {}

        self.player_states[username][piece_id] = {
            'x': x,
            'y': y,
            'isLocked': is_locked
        }

        # Only update database when piece is locked (reduces excessive writes)
        if is_locked:
            game_state = self.get_game_state()
            game_state['player_states'] = self.player_states
            self.update_game_state(game_state)

    def broadcast_team_progress(self):
        """Calculate and broadcast progress for all teams to the display"""
        total_pieces = self.rows * self.cols
        team_progress = {}

        for team_id, team_members in self.teams.items():
            # Track which pieces are correctly placed by ANY team member
            correctly_placed = set()

            for username in team_members:
                if username not in self.player_states:
                    continue

                player_pieces = self.player_states[username]
                for piece_id, piece_data in player_pieces.items():
                    if piece_data.get('isLocked', False):
                        correctly_placed.add(piece_id)

            # Calculate percentage
            pieces_locked = len(correctly_placed)
            percentage = (pieces_locked / total_pieces) * 100 if total_pieces > 0 else 0
            team_progress[team_id] = {
                'pieces_locked': pieces_locked,
                'total_pieces': total_pieces,
                'percentage': percentage
            }

        # Log progress for debugging
        if any(p['pieces_locked'] > 0 for p in team_progress.values()):
            print(f"CoopPuzzle: Broadcasting progress: {team_progress}")

        # Broadcast to display
        self.emit_to_display('coop_puzzle_progress', {
            'team_progress': team_progress
        })

    def check_team_completion(self):
        """Check if any team has completed the puzzle"""
        total_pieces = self.rows * self.cols

        for team_id, team_members in self.teams.items():
            # Track which pieces are correctly placed by ANY team member
            correctly_placed = set()

            for username in team_members:
                if username not in self.player_states:
                    continue

                player_pieces = self.player_states[username]
                for piece_id, piece_data in player_pieces.items():
                    if piece_data.get('isLocked', False):
                        correctly_placed.add(piece_id)

            # Check if all pieces are placed correctly
            if len(correctly_placed) == total_pieces:
                print(f"CoopPuzzle: {team_id} completed the puzzle!")
                return team_id

        return None

    def handle_game_completion(self, winning_team):
        """Handle when a team completes the puzzle"""
        print(f"CoopPuzzle: Handling completion for {winning_team}")

        # Award points to winning team members
        team_members = self.teams.get(winning_team, [])

        for username in team_members:
            user = User.query.filter_by(username=username).first()
            if user:
                user.overall_score += 1
                print(f"CoopPuzzle: Awarded 1 point to {username}")

        db.session.commit()

        # Update game state
        self.update_game_state({
            'status': 'completed',
            'game_over': True,
            'winning_team': winning_team
        })

        # Notify all players
        self.emit_to_all_players('coop_puzzle_completed', {
            'winning_team': winning_team,
            'team_members': team_members
        })

        # Notify display
        self.emit_to_display('coop_puzzle_completed', {
            'winning_team': winning_team,
            'team_members': team_members
        })

        # Notify admin
        self.emit_to_admin('coop_puzzle_game_over', {
            'winning_team': winning_team
        })

        print(f"CoopPuzzle: Game completed by {winning_team}")

    def end_game(self):
        """End the cooperative puzzle game"""
        print("CoopPuzzle: end_game called")

        # Update game state
        self.update_game_state({
            'status': 'ended'
        })

        # Call parent class end_game
        super().end_game()

        print("CoopPuzzle: Game ended successfully")

    def determine_winner(self):
        """Determine the winner - already handled in handle_game_completion"""
        pass
