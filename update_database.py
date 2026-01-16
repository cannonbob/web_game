#!/usr/bin/env python3
"""
Update database schema to add media columns to questions table
"""

from app import app
from db import db

def update_database():
    with app.app_context():
        print("Updating database schema...")
        
        # Get connection and execute raw SQL to add columns
        connection = db.engine.connect()
        
        # List of columns to add
        columns_to_add = [
            "ALTER TABLE questions ADD COLUMN question_type VARCHAR(20) DEFAULT 'text'",
            "ALTER TABLE questions ADD COLUMN media_url VARCHAR(500) DEFAULT NULL",
            "ALTER TABLE questions ADD COLUMN media_duration INT DEFAULT NULL",
            "ALTER TABLE questions ADD COLUMN spotify_track_id VARCHAR(100) DEFAULT NULL", 
            "ALTER TABLE questions ADD COLUMN auto_play BOOLEAN DEFAULT TRUE",
            "ALTER TABLE questions ADD COLUMN show_duration INT DEFAULT 30"
        ]
        
        # Execute each ALTER TABLE statement
        for sql in columns_to_add:
            try:
                connection.execute(sql)
                print(f"+ Added column: {sql.split('ADD COLUMN')[1].split()[0]}")
            except Exception as e:
                if "Duplicate column name" in str(e):
                    print(f"- Column already exists: {sql.split('ADD COLUMN')[1].split()[0]}")
                else:
                    print(f"x Error adding column: {e}")
                    
        # Close connection (commit not needed for ALTER TABLE)
        connection.close()
        
        print("Database schema update completed!")

if __name__ == "__main__":
    update_database()