#!/usr/bin/env python3
"""
Create a new game session featuring all media questions
"""

from app import app
from db import db
from models.game import Category, Question, SessionSetup, SessionCategory, SessionQuestion

def create_media_session():
    with app.app_context():
        print("Creating Media Demo Game Session...")
        
        # Check if a media session already exists
        existing_session = SessionSetup.query.filter_by(name="Media Demo Session").first()
        if existing_session:
            print("Media Demo Session already exists. Deleting old session...")
            # Delete old session data
            SessionQuestion.query.filter(
                SessionQuestion.session_category_id.in_(
                    db.session.query(SessionCategory.id).filter_by(session_id=existing_session.id)
                )
            ).delete(synchronize_session=False)
            SessionCategory.query.filter_by(session_id=existing_session.id).delete()
            db.session.delete(existing_session)
            db.session.commit()
        
        # Create new session
        media_session = SessionSetup(name="Media Demo Session")
        db.session.add(media_session)
        db.session.commit()
        print("Created new Media Demo Session")
        
        # Get all media questions grouped by type
        image_questions = Question.query.filter_by(question_type='image').all()
        audio_questions = Question.query.filter_by(question_type='audio').all()
        video_questions = Question.query.filter_by(question_type='video').all()
        
        # Get some regular text questions to fill out the board
        text_questions = Question.query.filter_by(question_type='text').limit(10).all()
        
        print(f"Found {len(image_questions)} image, {len(audio_questions)} audio, {len(video_questions)} video, {len(text_questions)} text questions")
        
        # Create categories for the session
        categories_data = [
            {
                "name": "Visual Questions",
                "questions": image_questions[:5],  # Up to 5 image questions
                "position": 1
            },
            {
                "name": "Music & Audio", 
                "questions": audio_questions[:5],  # Up to 5 audio questions
                "position": 2
            },
            {
                "name": "Video Questions",
                "questions": video_questions + text_questions[:5-len(video_questions)] if len(video_questions) < 5 else video_questions[:5],
                "position": 3
            },
            {
                "name": "Science",
                "questions": [q for q in text_questions if q.category.name == 'Science'][:5],
                "position": 4
            },
            {
                "name": "History", 
                "questions": [q for q in text_questions if q.category.name == 'History'][:5],
                "position": 5
            }
        ]
        
        # Create session categories and questions
        for cat_data in categories_data:
            if not cat_data["questions"]:
                continue
                
            # Get or create the category
            category = Category.query.filter_by(name=cat_data["name"]).first()
            if not category:
                category = Category(name=cat_data["name"], description=f"Questions for {cat_data['name']}")
                db.session.add(category)
                db.session.commit()
            
            # Create session category
            session_category = SessionCategory(
                session_id=media_session.id,
                category_id=category.id,
                position=cat_data["position"]
            )
            db.session.add(session_category)
            db.session.commit()
            
            # Add questions to the session category
            for i, question in enumerate(cat_data["questions"][:5]):  # Max 5 questions per category
                session_question = SessionQuestion(
                    session_category_id=session_category.id,
                    question_id=question.id,
                    position=i + 1,
                    used=False
                )
                db.session.add(session_question)
            
            print(f"Added category '{cat_data['name']}' with {len(cat_data['questions'][:5])} questions")
        
        db.session.commit()
        
        # Display session summary
        print("\n" + "="*60)
        print("MEDIA DEMO SESSION CREATED")
        print("="*60)
        
        session_categories = SessionCategory.query.filter_by(session_id=media_session.id).order_by(SessionCategory.position).all()
        
        for sc in session_categories:
            print(f"\nPosition {sc.position}: {sc.category.name}")
            session_questions = SessionQuestion.query.filter_by(session_category_id=sc.id).order_by(SessionQuestion.position).all()
            
            for sq in session_questions:
                q = sq.question
                media_info = ""
                if q.question_type == 'image' and q.media_url:
                    media_info = f" [IMAGE: {q.media_url}]"
                elif q.question_type == 'audio' and q.spotify_track_id:
                    media_info = f" [SPOTIFY: {q.spotify_track_id}]"
                elif q.question_type == 'audio' and q.media_url:
                    media_info = f" [AUDIO: {q.media_url}]"
                elif q.question_type == 'video' and q.media_url:
                    media_info = f" [VIDEO: {q.media_url}]"
                
                print(f"  {sq.position * 100}: {q.question_text[:50]}...{media_info}")
        
        print(f"\n✓ Session ID: {media_session.id}")
        print("✓ Ready to use in game board!")
        
        # Update the app to use this new session (make it the default)
        print("\nTo use this session, you can:")
        print("1. Update your app to use session ID", media_session.id)
        print("2. Or modify the /api/current_session route to return this session")

def update_api_to_use_media_session():
    """Helper function to show how to update the API"""
    with app.app_context():
        media_session = SessionSetup.query.filter_by(name="Media Demo Session").first()
        if media_session:
            print(f"\nTo make this the active session, modify app.py line ~210:")
            print(f"Change: session = SessionSetup.query.first()")
            print(f"To:     session = SessionSetup.query.get({media_session.id})")

if __name__ == "__main__":
    create_media_session()
    update_api_to_use_media_session()