from db import db
import datetime

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    overall_score = db.Column(db.Integer, default=0)
    match_me_score = db.Column(db.Integer, default=0)
    geo_guessr_score = db.Column(db.Integer, default=0)
    flappy_birds_score = db.Column(db.Integer, default=0)
    buzzer_score = db.Column(db.Integer, default=0)
    puzzle_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'overall_score': self.overall_score,
            'match_me_score': self.match_me_score,
            'geo_guessr_score': self.geo_guessr_score,
            'flappy_birds_score': self.flappy_birds_score,
            'buzzer_score': self.buzzer_score,
            'puzzle_score': self.puzzle_score
        }
