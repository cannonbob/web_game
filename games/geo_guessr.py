from games.base import BaseGame
from models.user import User
from db import db
from flask import session
import math

class GeoGuessrGame(BaseGame):
    def __init__(self, socketio, location_data=None, media_url=None):
        super().__init__(socketio)
        self.game_name = "geo_guessr"
        self.total_rounds = 1  # Always single round (question type only)
        self.current_round = 0
        self.current_location = None
        self.question_location = location_data  # Pre-set location from question
        self.question_media_url = media_url  # Media URL from question
    
    def initialize(self):
        """Initialize the GeoGuessr game"""
        super().initialize()
        
        # Register socket events
        self.register_socket_events()
        
        # Reset player scores for this game
        users = User.query.all()
        for user in users:
            user.geo_guessr_score = 0
        db.session.commit()
        
        # Set initial game state
        self.update_game_state({
            'status': 'ready',
            'current_round': 0,
            'total_rounds': self.total_rounds,
            'current_location': None,
            'played_locations': [],
            'player_guesses': {},
            'round_results': {},
            'player_total_distances': {}
        })
        
        # Notify players and display
        self.emit_to_all_players('geo_guessr_ready', {
            'total_rounds': self.total_rounds
        })
        self.emit_to_display('geo_guessr_init', {
            'users': [user.to_dict() for user in users if user.username != 'admin'],
            'total_rounds': self.total_rounds
        })
    
    def start_game(self):
        """Start the GeoGuessr game by starting the first round"""
        print("GeoGuessr: start_game() called - starting first round")
        self.is_active = True
        self.start_round()

    def register_socket_events(self):
        """Register SocketIO events for GeoGuessr game"""
        @self.socketio.on('geo_guessr_start_round')
        def handle_start_round(data):
            if session.get('username') == 'admin':
                self.start_round()

        @self.socketio.on('geo_guessr_end_round')
        def handle_end_round(data):
            if session.get('username') == 'admin':
                self.end_round()
        
        @self.socketio.on('geo_guessr_submit_guess')
        def handle_submit_guess(data):
            if session.get('username') != 'admin' and self.is_active:
                username = session.get('username')
                latitude = data.get('latitude')
                longitude = data.get('longitude')
                self.submit_guess(username, latitude, longitude)
    
    def start_round(self):
        """Start the single round of the GeoGuessr game"""
        game_state = self.get_game_state()

        # Increment round counter
        self.current_round = game_state.get('current_round', 0) + 1

        if self.current_round > self.total_rounds:
            # Round already completed, end the game
            self.end_game()
            return

        # Use pre-set location from question
        if not self.question_location:
            print("ERROR: No location data provided for geo_guessr question")
            return

        location = self.question_location

        # Get location name
        location_name = location.get('location_name') if isinstance(location, dict) else location.name

        # Update game state
        self.update_game_state({
            'status': 'active',
            'current_round': self.current_round,
            'current_location': location if isinstance(location, dict) else location.to_dict(),
            'player_guesses': {}
        })

        # Use media_url from question
        image_url = self.question_media_url if self.question_media_url else f"{location_name}.png"

        # Notify players and display
        self.emit_to_all_players('geo_guessr_round_started', {
            'round': self.current_round,
            'total_rounds': self.total_rounds
        })

        self.emit_to_display('geo_guessr_show_location', {
            'location_name': location_name,
            'image_url': image_url,
            'round': self.current_round,
            'total_rounds': self.total_rounds
        })
    
    def end_round(self):
        """End the current round and calculate results"""
        print(f"GeoGuessr: end_round called")
        game_state = self.get_game_state()
        current_location = game_state.get('current_location')
        player_guesses = game_state.get('player_guesses', {})
        player_total_distances = game_state.get('player_total_distances', {})
        print(f"GeoGuessr: Current location: {current_location}")
        print(f"GeoGuessr: Player guesses: {player_guesses}")
        
        if not current_location:
            print("GeoGuessr: ERROR - No current location found!")
            return
        
        # Calculate distances for all players and add to cumulative total
        print("GeoGuessr: Calculating distances...")
        results = {}
        for username, guess in player_guesses.items():
            print(f"GeoGuessr: Processing guess for {username}")
            distance = self.calculate_distance(
                current_location['latitude'], 
                current_location['longitude'],
                guess['latitude'],
                guess['longitude']
            )
            print(f"GeoGuessr: Distance calculated: {distance:.2f} km")
            
            # Add to cumulative distance
            if username not in player_total_distances:
                player_total_distances[username] = 0
            player_total_distances[username] += distance
            
            results[username] = {
                'guess': guess,
                'distance': distance,
                'total_distance': player_total_distances[username]
            }
            
            print(f"GeoGuessr: {username} total distance now: {player_total_distances[username]:.2f} km")
        
        # Add penalty for players who didn't submit a guess
        all_users = User.query.filter(User.username != 'admin').all()
        penalty_distance = 20000.0  # 20,000 km penalty
        
        for user in all_users:
            username = user.username
            if username not in player_guesses:
                print(f"GeoGuessr: {username} did not submit a guess, applying {penalty_distance}km penalty")
                
                # Add to cumulative distance
                if username not in player_total_distances:
                    player_total_distances[username] = 0
                player_total_distances[username] += penalty_distance
                
                # Add to results with penalty
                results[username] = {
                    'guess': {'latitude': 0, 'longitude': 0},  # Dummy coordinates for display
                    'distance': penalty_distance,
                    'total_distance': player_total_distances[username]
                }
                
                print(f"GeoGuessr: {username} total distance now: {player_total_distances[username]:.2f} km (with penalty)")
        
        print(f"GeoGuessr: All results: {results}")
        
        # Update round results
        round_results = game_state.get('round_results', {})
        round_results[str(self.current_round)] = {
            'location': current_location,
            'results': results
        }
        
        # Update game state with cumulative distances
        self.update_game_state({
            'status': 'round_ended',
            'round_results': round_results,
            'player_total_distances': player_total_distances
        })

        # Calculate points for display (before storing in database)
        PERFECT_GUESS_THRESHOLD = 0.25  # 250m in km
        winners = []
        for username, distance in player_total_distances.items():
            if distance <= PERFECT_GUESS_THRESHOLD:
                winners.append(username)

        # If no one is within 250m, award point to closest player
        if not winners:
            sorted_players = sorted(player_total_distances.items(), key=lambda x: x[1])
            if sorted_players:
                winners = [sorted_players[0][0]]

        print(f"GeoGuessr: Winners for display: {winners}")

        # Prepare display data with points
        display_data = {
            'round': self.current_round,
            'location': current_location,
            'players': []
        }

        for username, result in results.items():
            points = 1 if username in winners else 0
            display_data['players'].append({
                'username': username,
                'latitude': result['guess']['latitude'],
                'longitude': result['guess']['longitude'],
                'distance': result['distance'],
                'total_distance': result['total_distance'],
                'points': points
            })

        # Sort players by distance (ascending)
        display_data['players'].sort(key=lambda p: p['distance'])

        # Notify players and display
        self.emit_to_all_players('geo_guessr_round_ended', display_data)
        self.emit_to_display('geo_guessr_show_results', display_data)

        # Single round completed - calculate scores and store in database
        if self.current_round >= self.total_rounds:
            self.calculate_scores()
            # Don't emit all_rounds_completed - game will end when admin clicks end game
    
    def submit_guess(self, username, latitude, longitude):
        """Submit a guess for a player"""
        print(f"GeoGuessr: submit_guess called - username: {username}, lat: {latitude}, lng: {longitude}")
        game_state = self.get_game_state()
        print(f"GeoGuessr: Current game status: {game_state.get('status')}")
        
        # Only accept guesses if round is active
        if game_state.get('status') != 'active':
            print(f"GeoGuessr: Rejecting guess - round not active (status: {game_state.get('status')})")
            return
        
        # Store the guess
        player_guesses = game_state.get('player_guesses', {})
        player_guesses[username] = {
            'latitude': latitude,
            'longitude': longitude
        }
        print(f"GeoGuessr: Storing guess for {username}: lat={latitude}, lng={longitude}")
        print(f"GeoGuessr: All player guesses now: {player_guesses}")
        
        self.update_game_state({'player_guesses': player_guesses})
        
        # Notify the player
        print(f"GeoGuessr: Sending confirmation to {username}")
        self.emit_to_player(username, 'geo_guessr_guess_submitted', {
            'latitude': latitude,
            'longitude': longitude
        })
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate the distance between two coordinates in kilometers
        Using the Haversine formula"""
        # Convert to radians
        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        
        return c * r
    
    def calculate_scores(self):
        """Calculate scores after the round
        Award 1 point to all players within 250m of the location
        If no one is within 250m, award 1 point to the closest player"""
        print("GeoGuessr: Calculating scores...")
        game_state = self.get_game_state()
        player_total_distances = game_state.get('player_total_distances', {})

        if not player_total_distances:
            print("GeoGuessr: No player distances found!")
            return

        # Convert distances from km to meters for easier comparison
        PERFECT_GUESS_THRESHOLD = 0.25  # 250m in km

        # Find players within 250m
        winners = []
        for username, distance in player_total_distances.items():
            if distance <= PERFECT_GUESS_THRESHOLD:
                winners.append(username)

        # If no one is within 250m, award point to closest player
        if not winners:
            sorted_players = sorted(player_total_distances.items(), key=lambda x: x[1])
            if sorted_players:
                winners = [sorted_players[0][0]]  # Closest player

        print(f"GeoGuessr: Winners (within 250m or closest): {winners}")

        # Award points to winners
        for username in player_total_distances.keys():
            user = User.query.filter_by(username=username).first()
            if user:
                if username in winners:
                    user.geo_guessr_score = 1
                    print(f"GeoGuessr: Awarded 1 point to {username} (distance: {player_total_distances[username]:.2f}km)")
                else:
                    user.geo_guessr_score = 0
                    print(f"GeoGuessr: No points awarded to {username} (distance: {player_total_distances[username]:.2f}km)")

        db.session.commit()
        print("GeoGuessr: Scores committed to database")

    def end_game(self):
        """End the GeoGuessr game"""
        print("GeoGuessr: end_game called")
        
        # Update game state to indicate game has ended
        self.update_game_state({
            'status': 'game_ended'
        })
        
        # Call parent class end_game which sets is_active = False and calls determine_winner
        super().end_game()
        
        print("GeoGuessr: Game ended successfully")
    
    def determine_winner(self):
        """Determine the winner of the GeoGuessr game and award overall points"""
        print("GeoGuessr: determine_winner called")
        game_state = self.get_game_state()

        # Check if winner was already determined (prevent duplicate point awards)
        if game_state.get('winner_determined', False):
            print("GeoGuessr: Winner already determined, skipping point award")
            return

        users = User.query.filter(User.username != 'admin').all()

        # Award overall points: 1 point to all players who scored in geo_guessr
        winners = []
        for user in users:
            if user.geo_guessr_score > 0:  # They got a point (within 250m or closest)
                old_overall_score = user.overall_score
                user.overall_score += 1
                winners.append(user.username)
                print(f"GeoGuessr: Awarded 1 overall point to {user.username} (was {old_overall_score}, now {user.overall_score})")

        print("GeoGuessr: Committing overall score changes to database...")
        db.session.commit()
        print("GeoGuessr: Overall scores committed successfully")

        # Mark winner as determined
        self.update_game_state({'winner_determined': True})

        # Determine winner text
        if len(winners) > 1:
            winner_text = ', '.join(winners)
        elif len(winners) == 1:
            winner_text = winners[0]
        else:
            winner_text = 'No winners'

        print(f"GeoGuessr: Winners: {winner_text}")

        # Notify all players and display
        self.emit_to_all_players('geo_guessr_game_over', {
            'winner': winner_text,
            'scores': {user.username: user.geo_guessr_score for user in users}
        })

        self.emit_to_display('geo_guessr_game_over', {
            'winner': winner_text,
            'scores': {user.username: user.geo_guessr_score for user in users}
        })
        
        print("GeoGuessr: Game over notifications sent")
