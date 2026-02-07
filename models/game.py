from db import db
from sqlalchemy import event
import json

class GameState(db.Model):
    __tablename__ = 'game_state'

    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=False)
    active_game = db.Column(db.String(50), nullable=True)
    active_session_id = db.Column(db.Integer, db.ForeignKey('game_sessions.id'), nullable=True)
    game_data = db.Column(db.Text, nullable=True)  # JSON data for game state

    # Relationship to SessionSetup
    active_session = db.relationship('SessionSetup', foreign_keys=[active_session_id])

    def to_dict(self):
        return {
            'id': self.id,
            'is_active': self.is_active,
            'active_game': self.active_game,
            'active_session_id': self.active_session_id,
            'game_data': json.loads(self.game_data) if self.game_data else {}
        }

    def set_game_data(self, data):
        self.game_data = json.dumps(data)


class MatchMeGame(db.Model):
    """Legacy model for standalone match_me game (deprecated - use MatchMeCategory/MatchMeItem instead)"""
    __tablename__ = 'word_combi'

    id = db.Column(db.Integer, primary_key=True)
    word_question = db.Column(db.String(100), nullable=False)
    word_answer = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'word_question': self.word_question,
            'word_answer': self.word_answer
        }


class MatchMeCategory(db.Model):
    """Model for match_me game categories linked to questions."""
    __tablename__ = 'mm_categories'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, unique=True)
    category_name = db.Column(db.String(100), nullable=False)

    # Relationships
    question = db.relationship('Question', backref='match_me_category')
    items = db.relationship('MatchMeItem', backref='category', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<MatchMeCategory {self.id}: {self.category_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'category_name': self.category_name,
            'items': [item.to_dict() for item in self.items]
        }


class MatchMeItem(db.Model):
    """Model for individual items in match_me game."""
    __tablename__ = 'mm_items'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('mm_categories.id', ondelete='CASCADE'), nullable=False)
    question_text = db.Column(db.String(255), nullable=False)
    answer_text = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<MatchMeItem {self.id}: {self.question_text} -> {self.answer_text}>'

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'question_text': self.question_text,
            'answer_text': self.answer_text
        }


class GeoGuessrLocation(db.Model):
    __tablename__ = 'location'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    name = db.Column('location_name', db.String(100), nullable=False)
    latitude = db.Column('lat', db.Float, nullable=False)
    longitude = db.Column('lng', db.Float, nullable=False)
    loc_json = db.Column(db.JSON, nullable=True)  # GeoJSON for area-based locations

    # Relationship to question
    question = db.relationship('Question', backref='geo_location')

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'location_name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'loc_json': self.loc_json
        }


class PlayerGameState(db.Model):
    __tablename__ = 'player_game_state'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    game_type = db.Column(db.String(50), nullable=False)
    game_state = db.Column(db.Text, nullable=True)  # JSON data for player's game state
    
    user = db.relationship('User', backref=db.backref('game_states', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'game_type': self.game_type,
            'game_state': json.loads(self.game_state) if self.game_state else {}
        }
    
    def set_game_state(self, data):
        self.game_state = json.dumps(data)


class Category(db.Model):
    """Model for game categories."""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Relationships
    questions = db.relationship('Question', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'question_count': len(self.questions)
        }


class Question(db.Model):
    """Model for game questions."""
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer, default=1)  # 1-5 for difficulty/value
    
    # Media support
    question_type = db.Column(db.String(20), default='text')  # text, image, audio, video
    media_url = db.Column(db.String(500), nullable=True)  # File path or external URL
    media_duration = db.Column(db.Integer, nullable=True)  # Duration in seconds for audio/video
    spotify_track_id = db.Column(db.String(100), nullable=True)  # Spotify track ID
    
    # Media settings
    auto_play = db.Column(db.Boolean, default=True)  # Auto-play media when question opens
    show_duration = db.Column(db.Integer, default=30)  # How long to show/play before revealing answer

    # Multi-item support
    multi_item = db.Column(db.Integer, default=0)  # 0 = cumulative display (add items), 1 = replacement display (replace items)

    # Input question support
    input_expected = db.Column(db.Boolean, default=False)  # True if players need to submit answers

    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id', ondelete='CASCADE'), nullable=True)

    # Relationships
    question_items = db.relationship('QuestionItem', backref='question', lazy=True, cascade="all, delete-orphan")
    order_items = db.relationship('OrderItem', backref='question', lazy=True, cascade="all, delete-orphan")
    expected_answers = db.relationship('AnswerExpected', backref='question', lazy=True, cascade="all, delete-orphan")
    movie = db.relationship('Movie', backref='questions')
    
    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:20]}...>'
    
    def to_dict(self):
        result = {
            'id': self.id,
            'question_text': self.question_text,
            'answer': self.answer,
            'difficulty': self.difficulty,
            'category_id': self.category_id,
            'question_type': self.question_type,
            'media_url': self.media_url,
            'media_duration': self.media_duration,
            'spotify_track_id': self.spotify_track_id,
            'auto_play': self.auto_play,
            'show_duration': self.show_duration,
            'multi_item': self.multi_item,
            'input_expected': self.input_expected,
            'movie_id': self.movie_id,
            'items': [item.to_dict() for item in self.question_items],
            'order_items': [item.to_dict() for item in self.order_items],
            'expected_answers': [ans.to_dict() for ans in self.expected_answers],
            'sorting_categories': [cat.to_dict() for cat in self.sorting_categories],
            'sorting_items': [item.to_dict() for item in self.sorting_items]
        }

        # Include movie information if linked
        if self.movie:
            result['movie'] = {
                'id': self.movie.id,
                'title': self.movie.title,
                'year': self.movie.year
            }

        return result


class QuestionItem(db.Model):
    """Model for individual items in multi-item questions.
    Items with the same item_order are displayed together.
    """
    __tablename__ = 'question_items'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    item_text = db.Column(db.Text, nullable=True)  # Text content or image filename/path
    item_order = db.Column(db.Integer, nullable=False)  # Items with same order displayed together

    def __repr__(self):
        return f'<QuestionItem {self.id}: Question {self.question_id}, Order {self.item_order}>'

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'item_text': self.item_text,
            'item_order': self.item_order
        }


class OrderItem(db.Model):
    """Model for items in ordering game questions.
    Players must arrange these items in correct order by a given attribute.
    """
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)  # Name of the item (e.g., "Cheetah")
    item_value = db.Column(db.Float, nullable=False)  # Actual value to order by (e.g., 120.0 km/h)
    position = db.Column(db.Integer, nullable=False)  # Correct position in ordering (1-based)

    def __repr__(self):
        return f'<OrderItem {self.id}: {self.item_name} (position {self.position})>'

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'item_name': self.item_name,
            'item_value': self.item_value,
            'position': self.position
        }


class AnswerExpected(db.Model):
    """Model for expected answers to input questions."""
    __tablename__ = 'answers_expected'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    input_type = db.Column(db.String(20), default='normal')  # 'normal' (text), 'guess' (number), or 'ac' (auto-complete)
    hint = db.Column(db.String(50), nullable=False)  # Placeholder text for input form
    answer_raw = db.Column(db.String(255), nullable=False)  # Original answer
    answer_normalized = db.Column(db.String(255), nullable=False)  # Pre-normalized answer
    is_primary = db.Column(db.Boolean, default=True)  # Primary answer vs alternative
    rank = db.Column(db.Integer, nullable=True)  # Rank for Top 5 auto-complete questions (1-5)
    item_id = db.Column(db.Integer, db.ForeignKey('question_items.id'), nullable=True)  # FK to correct option for mc questions

    def __repr__(self):
        return f'<AnswerExpected {self.id}: Question {self.question_id}, Type {self.input_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'input_type': self.input_type,
            'hint': self.hint,
            'answer_raw': self.answer_raw,
            'answer_normalized': self.answer_normalized,
            'is_primary': self.is_primary,
            'rank': self.rank,
            'item_id': self.item_id
        }


class SortingCategory(db.Model):
    """Model for sorting game categories (2 per question)."""
    __tablename__ = 'sorting_categories'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    category_index = db.Column(db.Integer, nullable=False)  # 1 or 2

    # Relationships
    question = db.relationship('Question', backref='sorting_categories')
    items = db.relationship('SortingItem', backref='category', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SortingCategory {self.id}: {self.category_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'category_name': self.category_name,
            'category_index': self.category_index
        }


class SortingItem(db.Model):
    """Model for items to be sorted in the sorting game."""
    __tablename__ = 'sorting_items'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('sorting_categories.id', ondelete='CASCADE'), nullable=False)
    item_text = db.Column(db.String(255), nullable=False)

    # Relationships
    question = db.relationship('Question', backref='sorting_items')

    def __repr__(self):
        return f'<SortingItem {self.id}: {self.item_text}>'

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'category_id': self.category_id,
            'item_text': self.item_text
        }


class AnswerUser(db.Model):
    """Model for user-submitted answers to input questions."""
    __tablename__ = 'answers_user'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    round = db.Column(db.Integer, default=1, nullable=False)  # Which screenshot/round (1-based)
    answer_raw = db.Column(db.Text, nullable=False)  # User's raw input
    answer_normalized = db.Column(db.Text, nullable=False)  # Normalized version
    is_correct = db.Column(db.Boolean, default=False)  # Calculated correctness
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationships
    user = db.relationship('User', backref='answers')
    question = db.relationship('Question', backref='user_answers')

    def __repr__(self):
        return f'<AnswerUser {self.id}: User {self.user_id}, Question {self.question_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'question_id': self.question_id,
            'round': self.round,
            'answer_raw': self.answer_raw,
            'answer_normalized': self.answer_normalized,
            'is_correct': self.is_correct,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SessionSetup(db.Model):
    __tablename__ = 'game_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # Links to the selected categories for this session
    session_categories = db.relationship('SessionCategory', backref='session', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': str(self.created_at),
            'categories': [sc.to_dict() for sc in self.session_categories]
        }

class SessionCategory(db.Model):
    __tablename__ = 'session_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('game_sessions.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # Position on the board (1-5)
    
    # Relationship to the base category
    category = db.relationship('Category')
    
    # Selected questions for this category in this session
    selected_questions = db.relationship('SessionQuestion', backref='session_category', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'position': self.position,
            'category_name': self.category.name,
            'selected_questions': [sq.to_dict() for sq in self.selected_questions]
        }

class SessionQuestion(db.Model):
    __tablename__ = 'session_questions'

    id = db.Column(db.Integer, primary_key=True)
    session_category_id = db.Column(db.Integer, db.ForeignKey('session_categories.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # Position within category (1-5)
    used = db.Column(db.Boolean, default=False)

    # Relationship to the base question
    question = db.relationship('Question')

    def to_dict(self):
        question_dict = self.question.to_dict() if self.question else {}
        return {
            'id': self.id,
            'question_id': self.question_id,
            'position': self.position,
            'used': self.used,
            'question_text': self.question.question_text if self.question else '',
            'value': self.position * 100,
            # Include all media information from the question
            'question_type': question_dict.get('question_type', 'text'),
            'media_url': question_dict.get('media_url'),
            'spotify_track_id': question_dict.get('spotify_track_id'),
            'auto_play': question_dict.get('auto_play', True),
            'show_duration': question_dict.get('show_duration', 30),
            'answer': question_dict.get('answer', ''),
            'difficulty': question_dict.get('difficulty', 1)
        }


class Movie(db.Model):
    __tablename__ = 'movies'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    year = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'year': self.year
        }


class Product(db.Model):
    """Model for products (references existing table)."""
    __tablename__ = 'product'

    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(45), unique=True, nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'asin': self.asin,
            'product_name': self.product_name,
            'category': self.category
        }


class PriceGuessUser(db.Model):
    """Model for user price guesses."""
    __tablename__ = 'price_guess_user'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationships
    user = db.relationship('User', backref='price_guesses')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'answer': self.answer,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Event listener to auto-sync Question.answer from linked Movie.title
@event.listens_for(Question, 'before_insert')
@event.listens_for(Question, 'before_update')
def sync_movie_answer(mapper, connection, target):
    """Automatically sync the answer field from the linked movie's title"""
    if target.movie_id and target.movie:
        target.answer = target.movie.title