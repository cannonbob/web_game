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
