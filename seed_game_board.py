#!/usr/bin/env python3
"""
Seed script to create sample categories and questions for the game board
"""

from app import app
from db import db
from models.game import Category, Question, SessionSetup, SessionCategory, SessionQuestion

def seed_data():
    with app.app_context():
        print("Starting database seeding...")
        
        # Clear existing data
        SessionQuestion.query.delete()
        SessionCategory.query.delete()
        SessionSetup.query.delete()
        Question.query.delete()
        Category.query.delete()
        
        # Create categories
        categories_data = [
            {"name": "Science", "description": "Questions about science and technology"},
            {"name": "History", "description": "Questions about historical events"},
            {"name": "Geography", "description": "Questions about countries and places"},
            {"name": "Entertainment", "description": "Questions about movies, music, and pop culture"},
            {"name": "Sports", "description": "Questions about sports and athletes"}
        ]
        
        categories = []
        for cat_data in categories_data:
            category = Category(name=cat_data["name"], description=cat_data["description"])
            db.session.add(category)
            categories.append(category)
        
        db.session.commit()
        print(f"Created {len(categories)} categories")
        
        # Create questions for each category
        questions_data = {
            "Science": [
                {"text": "What is the chemical symbol for gold?", "answer": "Au", "difficulty": 1},
                {"text": "What planet is known as the Red Planet?", "answer": "Mars", "difficulty": 2},
                {"text": "What is the speed of light in vacuum?", "answer": "299,792,458 meters per second", "difficulty": 3},
                {"text": "What particle is known as the 'God particle'?", "answer": "Higgs boson", "difficulty": 4},
                {"text": "What is the most abundant element in the universe?", "answer": "Hydrogen", "difficulty": 5}
            ],
            "History": [
                {"text": "In which year did World War II end?", "answer": "1945", "difficulty": 1},
                {"text": "Who was the first person to walk on the moon?", "answer": "Neil Armstrong", "difficulty": 2},
                {"text": "Which empire was ruled by Julius Caesar?", "answer": "Roman Empire", "difficulty": 3},
                {"text": "What year did the Berlin Wall fall?", "answer": "1989", "difficulty": 4},
                {"text": "Who was the first Emperor of China?", "answer": "Qin Shi Huang", "difficulty": 5}
            ],
            "Geography": [
                {"text": "What is the capital of Australia?", "answer": "Canberra", "difficulty": 1},
                {"text": "Which river is the longest in the world?", "answer": "The Nile", "difficulty": 2},
                {"text": "What is the smallest country in the world?", "answer": "Vatican City", "difficulty": 3},
                {"text": "Which mountain range contains Mount Everest?", "answer": "The Himalayas", "difficulty": 4},
                {"text": "What is the deepest ocean trench?", "answer": "Mariana Trench", "difficulty": 5}
            ],
            "Entertainment": [
                {"text": "Who directed the movie 'Titanic'?", "answer": "James Cameron", "difficulty": 1},
                {"text": "Which band released the album 'Abbey Road'?", "answer": "The Beatles", "difficulty": 2},
                {"text": "What is the highest-grossing film of all time?", "answer": "Avatar (2009)", "difficulty": 3},
                {"text": "Who composed 'The Four Seasons'?", "answer": "Antonio Vivaldi", "difficulty": 4},
                {"text": "Which actor played the character of Tyler Durden?", "answer": "Brad Pitt", "difficulty": 5}
            ],
            "Sports": [
                {"text": "How many players are on a basketball team on the court?", "answer": "5", "difficulty": 1},
                {"text": "Which country won the 2018 FIFA World Cup?", "answer": "France", "difficulty": 2},
                {"text": "What is the maximum score possible in ten-pin bowling?", "answer": "300", "difficulty": 3},
                {"text": "Who holds the record for most Olympic gold medals?", "answer": "Michael Phelps", "difficulty": 4},
                {"text": "In which sport would you perform a slam dunk?", "answer": "Basketball", "difficulty": 5}
            ]
        }
        
        questions_created = 0
        for category in categories:
            category_questions = questions_data.get(category.name, [])
            for q_data in category_questions:
                question = Question(
                    question_text=q_data["text"],
                    answer=q_data["answer"],
                    difficulty=q_data["difficulty"],
                    category_id=category.id
                )
                db.session.add(question)
                questions_created += 1
        
        db.session.commit()
        print(f"Created {questions_created} questions")
        
        # Create a sample session
        session = SessionSetup(name="Sample Game Board Session")
        db.session.add(session)
        db.session.commit()
        
        # Add categories to session
        for i, category in enumerate(categories):
            session_category = SessionCategory(
                session_id=session.id,
                category_id=category.id,
                position=i + 1
            )
            db.session.add(session_category)
        
        db.session.commit()
        
        # Add questions to session categories
        for session_category in session.session_categories:
            category_questions = Question.query.filter_by(category_id=session_category.category_id).order_by(Question.difficulty).all()
            
            for i, question in enumerate(category_questions):
                if i < 5:  # Only take first 5 questions
                    session_question = SessionQuestion(
                        session_category_id=session_category.id,
                        question_id=question.id,
                        position=i + 1,
                        used=False
                    )
                    db.session.add(session_question)
        
        db.session.commit()
        print("Created sample session with categories and questions")
        print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_data()