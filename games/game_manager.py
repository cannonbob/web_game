from flask import session
from models.game import GameState
from db import db
import importlib
import json

class GameManager:
    def __init__(self, socketio):
        self.socketio = socketio
        self.games = {
            # 'match_me': 'games.match_me.MatchMeGame',  # Now only used as question type (mm)
            # 'geo_guessr': 'games.geo_guessr.GeoGuessrGame',  # Now only used as question type (gg)
            'flappy_birds': 'games.flappy_birds.FlappyBirdsGame',
            'price_guesser': 'games.price_guesser.PriceGuessrGame',
            'buzzer': 'games.buzzer.BuzzerGame',
            'coop_puzzle': 'games.coop_puzzle.CoopPuzzleGame',
            'movie_guesser': 'games.movie_guesser.MovieGuessrGame',  # Hidden from admin, used for movie questions
            'ordering_game': 'games.ordering_game.OrderingGame',  # Hidden from admin, used for ordering questions
            'tt': 'games.sorting_game.SortingGame'  # Hidden from admin, used for sorting questions
        }
        self.active_game = None

    def get_available_games(self):
        # Exclude movie_guesser, ordering_game, tt, geo_guessr, and match_me - they're only started when their respective questions are selected
        return [game for game in self.games.keys() if game not in ['movie_guesser', 'ordering_game', 'tt', 'geo_guessr', 'match_me']]

    def setup_utility_handlers(self, game_name):
        """Register socket handlers for a game without setting it as active.
        Used for games that provide utility features (like movie search) but aren't standalone games."""
        if game_name not in self.games:
            print(f"Game {game_name} not found for handler setup")
            return None

        try:
            # Import and instantiate the game class
            module_path, class_name = self.games[game_name].rsplit('.', 1)
            game_module = importlib.import_module(module_path)
            game_class = getattr(game_module, class_name)
            handler_instance = game_class(self.socketio)

            # Register socket events only (no initialization, no active_game setting)
            handler_instance.register_socket_events()
            print(f"Utility handlers registered for {game_name}")

            return handler_instance

        except Exception as e:
            print(f"Error setting up handlers for {game_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def start_game(self, game_name):
        print(f"GameManager.start_game called with: {game_name}")
        
        if game_name not in self.games:
            print(f"Game {game_name} not found in available games: {list(self.games.keys())}")
            return False
        
        try:
            # Update game state in database
            print(f"Updating game state in database...")
            game_state = GameState.query.first()
            if not game_state:
                game_state = GameState(is_active=True, active_game=game_name)
                db.session.add(game_state)
            else:
                game_state.is_active = True
                game_state.active_game = game_name
                game_state.game_data = '{}'
            
            db.session.commit()
            print(f"Database updated successfully")
            
            # Import and initialize the game
            module_path, class_name = self.games[game_name].rsplit('.', 1)
            print(f"Importing module: {module_path}, class: {class_name}")
            
            game_module = importlib.import_module(module_path)
            game_class = getattr(game_module, class_name)
            self.active_game = game_class(self.socketio)
            print(f"Game class instantiated successfully")
            
            # Initialize the game
            print(f"Calling game.initialize()...")
            self.active_game.initialize()
            print(f"Game initialized successfully")
            
            return True
            
        except Exception as e:
            print(f"Error starting game {game_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def end_game(self):
        if not self.active_game:
            return False

        # End the game FIRST (this needs to read game_data)
        self.active_game.end_game()

        # THEN update game state in database (clear game info but keep platform active)
        game_state = GameState.query.first()
        if game_state:
            # Keep is_active as True - platform stays active, just no game running
            game_state.active_game = None
            game_state.game_data = '{}'
            db.session.commit()

        self.active_game = None

        return True
    
    def get_active_game(self):
        return self.active_game
    
    def update_game_data(self, data):
        game_state = GameState.query.first()
        if game_state:
            current_data = json.loads(game_state.game_data) if game_state.game_data else {}
            current_data.update(data)
            game_state.game_data = json.dumps(current_data)
            db.session.commit()
