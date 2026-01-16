#!/usr/bin/env python3
"""
Enhanced seed script to create media questions for the game board
"""

from app import app
from db import db
from models.game import Category, Question, SessionSetup, SessionCategory, SessionQuestion

def seed_media_data():
    with app.app_context():
        print("Starting media question seeding...")
        
        # Get or create a Music category
        music_category = Category.query.filter_by(name='Music').first()
        if not music_category:
            music_category = Category(name='Music', description='Questions about songs, artists, and music')
            db.session.add(music_category)
            db.session.commit()
            print("Created Music category")
        
        # Create sample media questions
        media_questions = [
            # Image questions
            {
                "text": "What famous landmark is shown in this image?",
                "answer": "Aloha Tower",
                "difficulty": 1,
                "question_type": "image",
                "media_url": "/static/images/locations/Aloha Tower.png",
                "category": music_category  # You can change this to appropriate category
            },
            {
                "text": "Which ancient wonder is depicted here?",
                "answer": "Angkor Wat",
                "difficulty": 2,
                "question_type": "image",
                "media_url": "/static/images/locations/Angkor Wat.png",
                "category": music_category
            },
            
            # Audio questions with Spotify integration
            {
                "text": "What is the name of this famous song?",
                "answer": "Bohemian Rhapsody",
                "difficulty": 3,
                "question_type": "audio",
                "spotify_track_id": "4u7EnebtmKWzUH433cf5Qv",  # Bohemian Rhapsody by Queen
                "auto_play": True,
                "show_duration": 30,
                "category": music_category
            },
            {
                "text": "Who is the artist of this track?",
                "answer": "The Beatles",
                "difficulty": 2,
                "question_type": "audio",
                "spotify_track_id": "4pbJqGIASGPr0ZpGpnWkDn",  # Yesterday by The Beatles
                "auto_play": True,
                "show_duration": 25,
                "category": music_category
            },
            {
                "text": "From which album is this song?",
                "answer": "Abbey Road",
                "difficulty": 4,
                "question_type": "audio",
                "spotify_track_id": "6pKQC9tJcaw9Bl8k5y0VT3",  # Come Together by The Beatles
                "auto_play": True,
                "show_duration": 20,
                "category": music_category
            },
            
            # Example local audio file questions (you'll need to add actual files)
            {
                "text": "What instrument is playing the melody?",
                "answer": "Piano",
                "difficulty": 2,
                "question_type": "audio",
                "media_url": "/static/audio/piano_sample.mp3",  # You'll need to add this file
                "auto_play": True,
                "show_duration": 15,
                "category": music_category
            },
            
            # Video questions (example)
            {
                "text": "What movie is this scene from?",
                "answer": "The Lion King",
                "difficulty": 3,
                "question_type": "video",
                "media_url": "/static/videos/movie_clip.mp4",  # You'll need to add this file
                "auto_play": False,
                "show_duration": 30,
                "category": music_category
            }
        ]
        
        # Add questions to database
        questions_added = 0
        for q_data in media_questions:
            # Check if question already exists
            existing = Question.query.filter_by(question_text=q_data["text"]).first()
            if not existing:
                question = Question(
                    question_text=q_data["text"],
                    answer=q_data["answer"],
                    difficulty=q_data["difficulty"],
                    category_id=q_data["category"].id,
                    question_type=q_data["question_type"],
                    media_url=q_data.get("media_url"),
                    spotify_track_id=q_data.get("spotify_track_id"),
                    auto_play=q_data.get("auto_play", True),
                    show_duration=q_data.get("show_duration", 30)
                )
                db.session.add(question)
                questions_added += 1
        
        db.session.commit()
        print(f"Added {questions_added} new media questions")
        
        # Update existing session to include music category if not already present
        session = SessionSetup.query.first()
        if session:
            # Check if music category is already in session
            existing_music_category = SessionCategory.query.filter_by(
                session_id=session.id,
                category_id=music_category.id
            ).first()
            
            if not existing_music_category and len(session.session_categories) < 5:
                # Add music category to session
                next_position = len(session.session_categories) + 1
                if next_position <= 5:
                    session_category = SessionCategory(
                        session_id=session.id,
                        category_id=music_category.id,
                        position=next_position
                    )
                    db.session.add(session_category)
                    db.session.commit()
                    
                    # Add media questions to the session
                    music_questions = Question.query.filter_by(category_id=music_category.id).limit(5).all()
                    for i, question in enumerate(music_questions):
                        session_question = SessionQuestion(
                            session_category_id=session_category.id,
                            question_id=question.id,
                            position=i + 1,
                            used=False
                        )
                        db.session.add(session_question)
                    
                    db.session.commit()
                    print("Added Music category to existing session")
                else:
                    print("Session already has 5 categories - cannot add Music category")
            else:
                print("Music category already exists in session")
        
        print("Media question seeding completed!")

if __name__ == "__main__":
    seed_media_data()