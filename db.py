from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy.dialects.mysql import VARCHAR

db = SQLAlchemy()

load_dotenv('var.env')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB')
MYSQL_PORT = os.getenv('MYSQL_PORT')
MYSQL_SERVER = os.getenv('MYSQL_SERVER')
MYSQL_TABLE_USERS = os.getenv('MYSQL_TABLE_USERS')

def init_db(app):
    connector_string = f"mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    app.config['SQLALCHEMY_DATABASE_URI'] = connector_string
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Run migrations for schema updates
        run_migrations()


def run_migrations():
    """Run database migrations for schema updates"""
    from sqlalchemy import text

    # Migration: Add active_session_id column to game_state table
    try:
        # Check if column exists
        result = db.session.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = :db AND table_name = 'game_state' AND column_name = 'active_session_id'"
        ), {'db': MYSQL_DB})
        column_exists = result.scalar() > 0

        if not column_exists:
            db.session.execute(text(
                "ALTER TABLE game_state ADD COLUMN active_session_id INT NULL, "
                "ADD CONSTRAINT fk_game_state_session FOREIGN KEY (active_session_id) REFERENCES game_sessions(id)"
            ))
            db.session.commit()
            print("Migration: Added active_session_id column to game_state table")
    except Exception as e:
        print(f"Migration warning (active_session_id): {e}")
        db.session.rollback()
