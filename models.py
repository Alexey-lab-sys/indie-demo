from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """ Класс User представляет таблицу users в базе данных."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Связь с играми (один пользователь - много игр)
    games = db.relationship('Game', backref='developer', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'
    

class Game(db.Model):
    """ Класс Game представляет таблицу games в базе данных."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    genre = db.Column(db.String(50))
    platform = db.Column(db.String(50))
    demo_file_path = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    downloads_count = db.Column(db.Integer, default=0)
    is_approved = db.Column(db.Boolean, default=False)
    image_filename = db.Column(db.String(200), nullable=True)
    
    # Внешний ключ -> пользователь (ЭТА СТРОКА БЫЛА ПОТЕРЯНА!)
    developer_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<Game {self.title}>'


class Message(db.Model):
    """ Модель для хранения сообщений в чате """
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Внешний ключ -> пользователь
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Связь с пользователем
    user = db.relationship('User', backref='messages', lazy=True)
    
    def __repr__(self):
        return f'<Message {self.id}: {self.text[:20]}>'