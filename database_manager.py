from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import os
import logging

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # Load database credentials
        load_dotenv('var.env')
        self.mysql_host = os.getenv('MYSQL_HOST')
        self.mysql_user = os.getenv('MYSQL_USER')
        self.mysql_password = os.getenv('MYSQL_PASSWORD')
        self.mysql_db = os.getenv('MYSQL_DB')
        self.mysql_port = os.getenv('MYSQL_PORT')

        # Create direct database connection
        self.engine_string = f"mysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        self.engine = create_engine(self.engine_string)
        self.Session = sessionmaker(bind=self.engine)
        
        self.logger = logging.getLogger(__name__)
        self._initialized = True
        self.logger.info("DatabaseManager initialized")

    def get_session(self):
        """Get a new session for ORM operations"""
        return self.Session()

    def execute_direct_query(self, query, params=None):
        """Execute a direct SQL query and return results"""
        try:
            with self.engine.connect() as connection:
                if params:
                    result = connection.execute(query, params)
                else:
                    result = connection.execute(query)
                return result.fetchall()
        except SQLAlchemyError as e:
            self.logger.error(f"Database query error: {e}")
            raise

    def execute_direct_update(self, query, params=None):
        """Execute a direct SQL update and commit"""
        try:
            with self.engine.begin() as connection:
                if params:
                    result = connection.execute(query, params)
                else:
                    result = connection.execute(query)
                return result.rowcount
        except SQLAlchemyError as e:
            self.logger.error(f"Database update error: {e}")
            raise

    # Platform state management methods
    def set_platform_active(self, active=True, game=None):
        """
        Set the platform active state directly with SQL
        
        Args:
            active (bool): Whether the platform should be active
            game (str, optional): The active game name, or None if no specific game
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            active_value = 1 if active else 0
            game_value = f"'{game}'" if game else "NULL"
            
            query = f"UPDATE game_state SET is_active = {active_value}, active_game = {game_value} WHERE id = 1"
            rows_affected = self.execute_direct_update(query)
            
            self.logger.info(f"Platform state updated: active={active}, game={game}, rows_affected={rows_affected}")
            
            # Verify the update worked
            result = self.execute_direct_query("SELECT is_active, active_game FROM game_state WHERE id = 1")
            if result:
                db_active, db_game = result[0]
                self.logger.info(f"Verified database state: active={db_active}, game={db_game}")
                return True
            else:
                self.logger.warning("No game state found in database")
                return False
                
        except Exception as e:
            self.logger.error(f"Error setting platform state: {e}")
            return False
    
    def get_platform_state(self):
        """
        Get the current platform state directly with SQL
        
        Returns:
            dict: The platform state with keys 'is_active' and 'active_game'
        """
        try:
            result = self.execute_direct_query("SELECT is_active, active_game FROM game_state WHERE id = 1")
            if result:
                is_active, active_game = result[0]
                return {'is_active': bool(is_active), 'active_game': active_game}
            else:
                return {'is_active': False, 'active_game': None}
        except Exception as e:
            self.logger.error(f"Error getting platform state: {e}")
            return {'is_active': False, 'active_game': None}

# Create singleton instance
db_manager = DatabaseManager()