from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from sqlalchemy import func
import traceback
import os

# 引入项目自定义模块
from models import db, ChatLog, User
import graph_rag

app = Flask(__name__)

# ================= 1. 系统基础配置 =================
# 配置 MySQL 连接 (确保本地 MySQL 已创建 agri_qa 数据库)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@127.0.0.1:3306/agri_qa'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 【关键修复】：固定密钥，防止重启后 Session 失效
app.config['SECRET_KEY'] = 'nong_wenda_fixed_secret_key_2026'

# 初始化数据库
db.init_app(app)

with app.app_context():
    # 自动创建所有定义的数据库表
    db.create_all()
    # 自动检测并初始化默认管理员 (账号: admin / 密码: 123456)
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin_user = User(username='admin', role='admin', phone='13800138000')
        admin_user.set_password('123456')
        db.session.add(admin_user)
        db.session.commit()
        print("✅ 默认管理员账号已创建: admin / 123456")
    else:
        # 确保现有 admin 账号的权限是正确的
        if admin.role != 'admin':
            admin.role = 'admin'
            db.session.commit()
            print("✅ 已修正 admin 账号权限")
    print("✅ 系统就绪：MySQL 数据库已链接。")


# ================= 2. 用户身份认证与权限管理 =================

@app.route('/login')
def login_page():
    """渲染登录/注册页面"""
    return render_template('login.html')


@app.route('/api/register', methods=['POST'])
def register():
    """新用户注册接口"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if User.query.filter_by(username=username).first():
            return jsonify({"code": 400, "msg": "该用户名已被注册"})

        user = User(username=username, role='user')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return jsonify({"code": 200, "msg": "注册成功，请登录"})
    except Exception:
        return jsonify({"code": 500, "msg": "注册失败，请稍后再试"})


@app.route('/api/login', methods=['POST'])
def login():
    """用户登录接口"""
    data = request.json
    user = User.query.filter_by(username=data.get('username')).first()

    if user and user.check_password(data.get('password')):
        # 记录会话信息
        session.clear()  # 登录前先清空旧的 session 碎片
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        print(f"🔑 用户 {user.username} 登录成功，角色为: {user.role}")
        return jsonify({"code": 200, "msg": "登录成功", "role": user.role})

    return jsonify({"code": 400, "msg": "用户名或密码错误"})


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login_page'))


# ================= 3. 核心业务：C端智能对话接口 =================

@app.route('/')
def index():
    """渲染 C 端聊天主页面"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """GraphRAG 问答引擎接口"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        user_location = data.get('location', None)
        is_voice = data.get('is_voice', False)

        if not user_message:
            return jsonify({"code": 400, "msg": "消息内容不能为空"})

        intent = graph_rag.extract_intent(user_message)
        kg_data = []
        if intent and intent.get('crop'):
            kg_data = graph_rag.query_neo4j(intent, auto_location=user_location)

        final_reply = graph_rag.generate_final_answer(user_message, kg_data, auto_location=user_location)

        new_log = ChatLog(
            user_id=session.get('user_id'),
            user_query=user_message,
            extracted_intent=intent,
            bot_reply=final_reply,
            location=user_location,
            is_voice=is_voice
        )
        db.session.add(new_log)
        db.session.commit()

        return jsonify({
            "code": 200,
            "msg": "success",
            "reply": final_reply,
            "card_data": kg_data
        })

    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"code": 500, "msg": "系统繁忙"})


# ================= 4. 后台管理与数据分析接口 =================

@app.route('/admin')
def admin_page():
    """渲染后台管理系统 (权限校验升级)"""
    # 【调试打印】
    print(f"🔍 访问管理后台 - 当前 Session 角色: {session.get('role')}")

    if session.get('role') != 'admin':
        print("🚫 拒绝访问：权限不足，重定向至登录页")
        return redirect(url_for('login_page'))

    return render_template('admin.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    status = {"api": "running", "mysql": "unknown", "neo4j": "connected"}
    try:
        db.session.execute(func.now())
        status["mysql"] = "connected"
    except Exception as e:
        status["mysql"] = f"error: {str(e)}"
    return jsonify(status)


@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    """数据大屏接口"""
    if session.get('role') != 'admin':
        return jsonify({"code": 403, "msg": "未授权"})

    try:
        crop_stats = db.session.query(
            func.json_unquote(func.json_extract(ChatLog.extracted_intent, '$.crop')).label('crop'),
            func.count(ChatLog.id)
        ).group_by('crop').all()

        loc_stats = db.session.query(
            ChatLog.location, func.count(ChatLog.id)
        ).group_by(ChatLog.location).all()

        return jsonify({
            "crops": [{"name": str(c[0]), "value": c[1]} for c in crop_stats if c[0] and str(c[0]) != 'null'],
            "locations": [{"name": l[0], "value": l[1]} for l in loc_stats if l[0]]
        })
    except Exception as e:
        return jsonify({"crops": [], "locations": []})


@app.route('/api/admin/kg/add', methods=['POST'])
def add_kg_node():
    """图谱内容新增"""
    if session.get('role') != 'admin':
        return jsonify({"code": 403, "msg": "未授权"})

    data = request.json
    success = graph_rag.add_variety_to_kg(data)
    if success:
        return jsonify({"code": 200, "msg": "新品种已成功写入知识图谱"})
    return jsonify({"code": 500, "msg": "图谱写入失败"})


if __name__ == '__main__':
    # host='0.0.0.0' 允许局域网访问，debug=False 保护显存
    app.run(debug=False, host='0.0.0.0', port=5000)