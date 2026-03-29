from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# 实例化 SQLAlchemy 对象，稍后在 app.py 中与 Flask app 绑定
db = SQLAlchemy()


class User(db.Model):
    """
    用户表：用于后台管理和用户身份记录
    加入了密码和角色控制，支撑 C 端登录与 B 端后台权限
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), nullable=False, unique=True, comment="用户名/微信昵称")
    # --- 密码与权限控制字段 ---
    password_hash = db.Column(db.String(255), nullable=True, comment="加密后的密码(若是微信授权可为空)")
    role = db.Column(db.String(20), default='user', comment="系统角色: 'user' 或 'admin'")

    phone = db.Column(db.String(20), nullable=True, comment="联系方式")
    created_at = db.Column(db.DateTime, default=datetime.now, comment="注册时间")

    # ================= 新增：表关联关系 =================
    # 一个用户对应一个农场 (一对一)，uselist=False 确保返回单条数据
    farm_info = db.relationship('FarmInfo', backref='user', uselist=False, cascade="all, delete-orphan")
    # 一个用户对应多个账本记录 (一对多)
    ledgers = db.relationship('Ledger', backref='user', lazy=True, cascade="all, delete-orphan")

    # --- 密码安全处理方法 ---
    def set_password(self, password):
        """将明文密码转化为哈希值存储"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """校验密码是否正确"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "phone": self.phone,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self):
        return f"<User {self.username} (Role: {self.role})>"


class ChatLog(db.Model):
    """
    问答日志表：记录用户的每一次提问及系统的回答。
    """
    __tablename__ = 'chat_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment="关联用户ID")

    # --- 核心对话数据 ---
    user_query = db.Column(db.Text, nullable=False, comment="用户的原始自然语言提问")
    extracted_intent = db.Column(db.JSON, nullable=True, comment="Qwen提取的结构化意图")
    bot_reply = db.Column(db.Text, nullable=False, comment="系统最终反馈给用户的解答")

    # --- 特色功能数据 ---
    location = db.Column(db.String(100), nullable=True, comment="前端传入的地理位置")
    is_voice = db.Column(db.Boolean, default=False, comment="是否由语音转换")

    created_at = db.Column(db.DateTime, default=datetime.now, comment="交互时间")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_query": self.user_query,
            "extracted_intent": self.extracted_intent,
            "bot_reply": self.bot_reply,
            "location": self.location,
            "is_voice": self.is_voice,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self):
        return f"<ChatLog {self.id}: {self.user_query[:10]}...>"


# ================= 新增：个人农场相关模型 =================

class FarmInfo(db.Model):
    """
    我的土地信息表：记录用户的农场基本情况
    用于给 AI 提供更精准的个性化推荐上下文（如基于土壤类型推荐）
    """
    __tablename__ = 'farm_info'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, comment="关联用户ID(一对一)")

    area = db.Column(db.Float, default=0.0, comment="种植面积(亩)")
    soil_type = db.Column(db.String(50), default='', comment="土壤类型：如 沙土、黏土、壤土")
    main_crop = db.Column(db.String(100), default='', comment="主要种植作物：如 玉米、小麦")
    location = db.Column(db.String(100), default='', comment="农场具体位置")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "area": self.area,
            "soil_type": self.soil_type,
            "main_crop": self.main_crop,
            "location": self.location
        }

    def __repr__(self):
        return f"<FarmInfo UserID:{self.user_id} - {self.area}亩 {self.main_crop}>"


class Ledger(db.Model):
    """
    农事账本记录表：记录农户的每一笔收支
    """
    __tablename__ = 'ledgers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment="关联用户ID")

    record_date = db.Column(db.String(20), nullable=False, comment="发生日期 YYYY-MM-DD")
    type = db.Column(db.String(10), nullable=False, comment="收支类型：'income' (收入) 或 'expense' (支出)")
    category = db.Column(db.String(50), nullable=False, comment="类别：如 种子、化肥、农药、卖粮")
    amount = db.Column(db.Float, nullable=False, comment="金额")
    notes = db.Column(db.String(200), default='', comment="备注明细")

    created_at = db.Column(db.DateTime, default=datetime.now, comment="记录创建时间")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "record_date": self.record_date,
            "type": self.type,
            "category": self.category,
            "amount": self.amount,
            "notes": self.notes,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self):
        return f"<Ledger {self.record_date}: {self.type} {self.amount}>"