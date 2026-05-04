from datetime import timedelta
import os
import traceback
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from sqlalchemy import or_
from models import db, User, Product, Order, ChatLog
import graph_rag

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SC_DATABASE_URI', 'mysql+pymysql://root:123456@127.0.0.1:3306/shangcheng_qa')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SC_SECRET_KEY', 'shangcheng_secret_2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
db.init_app(app)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('123456')
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username, password = data.get('username', '').strip(), data.get('password', '').strip()
    if not username or not password:
        return jsonify({'code': 400, 'msg': '用户名和密码不能为空'})
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 400, 'msg': '用户名已存在'})
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '注册成功'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=data.get('username', '')).first()
    if not user or not user.check_password(data.get('password', '')):
        return jsonify({'code': 400, 'msg': '用户名或密码错误'})
    session.clear()
    session.permanent = True
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    return jsonify({'code': 200, 'msg': '登录成功', 'role': user.role})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'code': 400, 'msg': '消息不能为空'})
    try:
        intent = graph_rag.extract_intent(user_message)
        kg_data = graph_rag.query_kg(intent)
        order_info = None
        order_no = (intent or {}).get('order_no')
        if order_no:
            order = Order.query.filter_by(order_no=order_no, user_id=session['user_id']).first()
            if order:
                order_info = {
                    'order_no': order.order_no,
                    'status': order.status,
                    'total_amount': order.total_amount,
                    'logistics_company': order.logistics_company,
                    'tracking_no': order.tracking_no,
                }
        reply = graph_rag.generate_final_answer(user_message, intent, kg_data, order_info)
        log = ChatLog(user_id=session['user_id'], user_query=user_message, extracted_intent=intent, bot_reply=reply, used_kg=bool(kg_data))
        db.session.add(log)
        db.session.commit()
        return jsonify({'code': 200, 'reply': reply, 'card_data': kg_data})
    except Exception:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '系统繁忙'})

@app.route('/api/chat/history')
def history():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    logs = ChatLog.query.filter_by(user_id=session['user_id']).order_by(ChatLog.id.desc()).limit(50).all()
    return jsonify({'code': 200, 'data': [{'query': l.user_query, 'reply': l.bot_reply, 'time': l.created_at.strftime('%Y-%m-%d %H:%M:%S')} for l in logs]})

@app.route('/api/products', methods=['GET'])
def products():
    q = request.args.get('q', '').strip()
    query = Product.query
    if q:
        query = query.filter(or_(Product.name.contains(q), Product.category.contains(q), Product.sku.contains(q)))
    rows = query.order_by(Product.id.desc()).limit(100).all()
    return jsonify({'code': 200, 'data': [{'sku': r.sku, 'name': r.name, 'category': r.category, 'price': r.price, 'stock': r.stock} for r in rows]})

@app.route('/api/orders', methods=['GET'])
def orders():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    rows = Order.query.filter_by(user_id=session['user_id']).order_by(Order.id.desc()).all()
    return jsonify({'code': 200, 'data': [{'order_no': r.order_no, 'status': r.status, 'total_amount': r.total_amount, 'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')} for r in rows]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
