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
    # --- 新增：密码与权限控制字段 ---
    password_hash = db.Column(db.String(255), nullable=True, comment="加密后的密码(若是微信授权可为空)")
    role = db.Column(db.String(20), default='user', comment="系统角色: 'user' 或 'admin'")

    phone = db.Column(db.String(20), nullable=True, comment="联系方式")
    created_at = db.Column(db.DateTime, default=datetime.now, comment="注册时间")

    # --- 新增：密码安全处理方法 ---
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
    这是系统的核心数据资产，用于：
    1. 统计热门提问（如高频查询的品种/病害）。
    2. 后期复盘，优化 Qwen 大模型的 prompt。
    3. 支持 LBS（定位）和 ASR（语音）的数据打点记录。
    """
    __tablename__ = 'chat_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=True, comment="关联用户ID(未登录/匿名测试时为Null)")

    # --- 核心对话数据 ---
    user_query = db.Column(db.Text, nullable=False, comment="用户的原始自然语言提问")
    extracted_intent = db.Column(db.JSON, nullable=True, comment="Qwen提取的结构化意图(作物、地区、病害等)")
    bot_reply = db.Column(db.Text, nullable=False, comment="系统最终反馈给用户的解答")

    # --- 特色功能数据 (LBS / ASR) ---
    location = db.Column(db.String(100), nullable=True, comment="前端传入的地理位置，用于因地制宜推荐")
    is_voice = db.Column(db.Boolean, default=False, comment="标记该问题是否由语音(ASR)转换而来")

    # --- 时间戳 ---
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
        # 截取前10个字作为预览
        return f"<ChatLog {self.id}: {self.user_query[:10]}...>"