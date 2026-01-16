from games.base import BaseGame
from models.user import User
from models.game import Product
from db import db
from flask import session

# Try to import amazon_scraper, but make it optional
try:
    from amazon_scraper import fetch_amazon_price
    SCRAPER_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Amazon scraper not available: {e}")
    print("Price fetching will be disabled. Admin must enter prices manually.")
    SCRAPER_AVAILABLE = False
    fetch_amazon_price = None

class PriceGuessrGame(BaseGame):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.game_name = "price_guesser"

    def initialize(self):
        """Initialize the Price Guesser game WITHOUT scraping"""
        super().initialize()

        # Don't select product yet - wait until admin clicks "Show Content"
        print("Price Guesser initialized. Waiting for admin to reveal content before scraping.")

    def show_next_product(self):
        """Select and show a random product"""
        from models.game import PriceGuessUser

        # Get a random product from database
        product = Product.query.order_by(db.func.random()).first()

        if not product:
            print("ERROR: No products found in database!")
            return False

        print(f"Auto-selected product: {product.product_name} (ASIN: {product.asin})")

        # Fetch current price and image from Amazon (fresh data, not stored in DB)
        # This is SYNCHRONOUS - will block until scraping is complete
        price = None
        image_url = None
        if SCRAPER_AVAILABLE:
            print(f"[SCRAPING START] Fetching price and image for ASIN: {product.asin}...")
            try:
                price, image_url = fetch_amazon_price(product.asin)
                print(f"[SCRAPING COMPLETE] Price: {price}€, Image: {'Yes' if image_url else 'No'}")
                if not price:
                    print("WARNING: Could not fetch price from Amazon")
                if not image_url:
                    print("WARNING: Could not fetch image from Amazon")
            except Exception as e:
                print(f"ERROR fetching price and image: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("WARNING: Price scraper not available. Admin must enter price manually.")

        # IMPORTANT: Only proceed after scraping is complete
        print(f"[PRODUCT DATA] ID={product.id}, ASIN={product.asin}, Name={product.product_name}")
        print(f"[PRODUCT DATA] Price={price}, Image URL={'Set' if image_url else 'Not Set'}")

        # Clear previous guesses for this product (cleanup)
        PriceGuessUser.query.filter_by(product_id=product.id).delete()
        db.session.commit()

        # Get existing question_text if any (from question-driven mode)
        existing_data = self.get_game_state()
        question_text = existing_data.get('question_text', 'Guess the price!') if existing_data else 'Guess the price!'

        # Store current product in game_data (price and image stored temporarily here)
        game_state_data = {
            'status': 'active',
            'question_text': question_text,
            'current_product': {
                'id': product.id,
                'asin': product.asin,
                'name': product.product_name,
                'price': price,  # Stored in game state, not in database
                'image_url': image_url
            }
        }
        print(f"[GAME STATE] Updating with: {game_state_data}")
        self.update_game_state(game_state_data)

        # Notify EVERYONE (players, display, admin) about new product
        # Using broadcast to ensure display receives it regardless of room timing
        amazon_url = f'https://www.amazon.de/dp/{product.asin}?gameMode=true'
        product_data = {
            'product_id': product.id,
            'asin': product.asin,
            'product_name': product.product_name,
            'url': amazon_url,
            'price': price,  # Pass fetched price to clients
            'image_url': image_url
        }
        print(f"[EMIT] Broadcasting display_open_amazon with ASIN: {product.asin}")
        self.socketio.emit('display_open_amazon', product_data, broadcast=True)

        # Notify admin about product and price
        self.emit_to_admin('product_price_loaded', {
            'product_id': product.id,
            'product_name': product.product_name,
            'price': price,
            'image_url': image_url
        })

        print(f"Product ready. Display will open Amazon window: {amazon_url}")
        if price:
            print(f"Current price: {price}€")

        return True

    def register_socket_events(self):
        """Register SocketIO events for Price Guesser game"""
        @self.socketio.on('pg_question_selected')
        def handle_pg_question_selected(data):
            """Handle when a PG question is selected from game board"""
            print(f"PG question selected: {data}")

            # Store question text in game data (NO scraping yet)
            question_text = data.get('question_text', 'Guess the price!')
            self.update_game_state({
                'question_text': question_text,
                'scraping_status': 'not_started'  # Track scraping state
            })

            # Emit event to display with question text (category) - instant forwarding
            self.socketio.emit('pg_question_ready', {
                'question_text': question_text
            }, broadcast=True)

            print("Question text stored. Scraping will start when admin clicks 'Show Content'.")

    def start_game(self):
        """Start the Price Guesser game"""
        self.is_active = True
        self.update_game_state({
            'status': 'active'
        })

        # Notify players and display
        self.emit_to_all_players('price_guesser_started', {})
        self.emit_to_display('price_guesser_started', {})
