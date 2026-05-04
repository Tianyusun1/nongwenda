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

@app.route('/mall')
def mall_home():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('mall.html')

@app.route('/product/<int:product_id>')
def product_detail_page(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('product_detail.html', product_id=product_id)

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
    role = data.get('role', 'user')
    user = User(username=username, role=role if role in ['user', 'merchant'] else 'user')
    user.set_password(password)
    if user.role == 'merchant':
        user.shop_name = data.get('shop_name', '').strip()
        user.merchant_status = 'pending'
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
        product_hint = (intent or {}).get('product_name')
        db_products = []
        if product_hint:
            rows = Product.query.filter(Product.status == 'on_sale', Product.name.contains(product_hint)).limit(3).all()
            db_products = [{'id': p.id, 'name': p.name, 'price': p.price, 'stock': p.stock} for p in rows]
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
        if db_products:
            links = '\n'.join([f"- {p['name']}：/product/{p['id']}（¥{p['price']}）" for p in db_products])
            reply = f"{reply}\n\n为您推荐本店商品：\n{links}"
        log = ChatLog(user_id=session['user_id'], user_query=user_message, extracted_intent=intent, bot_reply=reply, used_kg=bool(kg_data))
        db.session.add(log)
        db.session.commit()
        return jsonify({'code': 200, 'reply': reply, 'card_data': kg_data, 'recommend_products': db_products})
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
    rows = query.filter_by(status='on_sale').order_by(Product.id.desc()).limit(100).all()
    return jsonify({'code': 200, 'data': [{'id': r.id, 'sku': r.sku, 'name': r.name, 'category': r.category, 'price': r.price, 'stock': r.stock, 'merchant_id': r.merchant_id} for r in rows]})

@app.route('/api/products/<int:product_id>', methods=['GET'])
def product_detail(product_id):
    row = Product.query.filter_by(id=product_id).first()
    if not row:
        return jsonify({'code': 404, 'msg': '商品不存在'})
    return jsonify({'code': 200, 'data': {'id': row.id, 'sku': row.sku, 'name': row.name, 'category': row.category, 'price': row.price, 'stock': row.stock, 'desc': row.desc, 'status': row.status}})

@app.route('/api/orders', methods=['GET'])
def orders():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    rows = Order.query.filter_by(user_id=session['user_id']).order_by(Order.id.desc()).all()
    return jsonify({'code': 200, 'data': [{'order_no': r.order_no, 'status': r.status, 'total_amount': r.total_amount, 'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')} for r in rows]})

@app.route('/api/orders/<order_no>/receive', methods=['POST'])
def order_receive(order_no):
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    order = Order.query.filter_by(order_no=order_no, user_id=session['user_id']).first()
    if not order:
        return jsonify({'code': 404, 'msg': '订单不存在'})
    if order.status != 'shipped':
        return jsonify({'code': 400, 'msg': '当前订单不可收货'})
    from datetime import datetime
    order.status = 'received'
    order.received_at = datetime.now()
    db.session.commit()
    return jsonify({'code': 200, 'msg': '确认收货成功'})

@app.route('/api/merchant/products', methods=['POST'])
def merchant_create_product():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    user = User.query.get(session['user_id'])
    if not user or user.role != 'merchant' or user.merchant_status != 'approved':
        return jsonify({'code': 403, 'msg': '商家未审核通过，不能上架商品'})
    data = request.get_json(silent=True) or {}
    p = Product(
        sku=data.get('sku', '').strip(),
        name=data.get('name', '').strip(),
        category=data.get('category', '').strip() or '默认类目',
        price=float(data.get('price', 0)),
        stock=int(data.get('stock', 0)),
        desc=data.get('desc', '').strip(),
        merchant_id=user.id,
        status='on_sale'
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '上架成功', 'id': p.id})

@app.route('/api/merchant/products/<int:product_id>/status', methods=['POST'])
def merchant_switch_product_status(product_id):
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    user = User.query.get(session['user_id'])
    p = Product.query.filter_by(id=product_id, merchant_id=session['user_id']).first()
    if not user or user.role != 'merchant' or not p:
        return jsonify({'code': 403, 'msg': '无权限'})
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status not in ['on_sale', 'off_sale']:
        return jsonify({'code': 400, 'msg': '状态非法'})
    p.status = new_status
    db.session.commit()
    return jsonify({'code': 200, 'msg': '状态更新成功'})

@app.route('/api/merchant/orders/<order_no>/ship', methods=['POST'])
def merchant_ship_order(order_no):
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})
    user = User.query.get(session['user_id'])
    if not user or user.role != 'merchant':
        return jsonify({'code': 403, 'msg': '无权限'})
    data = request.get_json(silent=True) or {}
    order = Order.query.filter_by(order_no=order_no).first()
    if not order:
        return jsonify({'code': 404, 'msg': '订单不存在'})
    order.status = 'shipped'
    order.logistics_company = data.get('logistics_company', '')
    order.tracking_no = data.get('tracking_no', '')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '发货成功'})

@app.route('/api/admin/merchant/review', methods=['POST'])
def admin_review_merchant():
    if str(session.get('role', '')).strip() != 'admin':
        return jsonify({'code': 403, 'msg': '未授权'})
    data = request.get_json(silent=True) or {}
    merchant = User.query.filter_by(id=data.get('merchant_id'), role='merchant').first()
    if not merchant:
        return jsonify({'code': 404, 'msg': '商家不存在'})
    status = data.get('status')
    if status not in ['approved', 'rejected']:
        return jsonify({'code': 400, 'msg': '审核状态非法'})
    merchant.merchant_status = status
    db.session.commit()
    return jsonify({'code': 200, 'msg': '审核完成'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
