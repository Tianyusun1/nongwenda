from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'sc_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'sc_products'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    desc = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Order(db.Model):
    __tablename__ = 'sc_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('sc_users.id'), nullable=False)
    status = db.Column(db.String(32), default='pending')
    total_amount = db.Column(db.Float, default=0)
    address = db.Column(db.String(255), default='')
    logistics_company = db.Column(db.String(64), default='')
    tracking_no = db.Column(db.String(64), default='')
    created_at = db.Column(db.DateTime, default=datetime.now)

class ChatLog(db.Model):
    __tablename__ = 'sc_chat_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('sc_users.id'))
    user_query = db.Column(db.Text, nullable=False)
    extracted_intent = db.Column(db.JSON)
    bot_reply = db.Column(db.Text, nullable=False)
    used_kg = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
