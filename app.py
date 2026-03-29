from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from sqlalchemy import func
from datetime import timedelta
import traceback
import os
import csv
import io
import json

# 【注意】这里引入了新增加的模型 FarmInfo 和 Ledger
from models import db, ChatLog, User, FarmInfo, Ledger
import graph_rag

app = Flask(__name__)

# ================= 1. 系统基础配置 =================
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@127.0.0.1:3306/agri_qa'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'nong_wenda_fixed_secret_key_2026'

app.config.update(
    SESSION_COOKIE_NAME='NONG_WENDA_SESSION',
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_REFRESH_EACH_REQUEST=True
)

db.init_app(app)

with app.app_context():
    db.create_all()  # 自动在 MySQL 中创建 farm_info 和 ledgers 新表
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin_user = User(username='admin', role='admin', phone='13800138000')
        admin_user.set_password('123456')
        db.session.add(admin_user)
        db.session.commit()
        print("✅ 默认管理员账号已创建: admin / 123456")
    else:
        if admin.role != 'admin':
            admin.role = 'admin'
            db.session.commit()
    print("✅ 系统就绪：MySQL 数据库已链接。")


# ================= 2. 用户身份认证 =================

@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/api/register', methods=['POST'])
def register():
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
    data = request.json
    user = User.query.filter_by(username=data.get('username')).first()

    if user and user.check_password(data.get('password')):
        session.clear()
        session.permanent = True
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = str(user.role).strip()
        session.modified = True
        return jsonify({"code": 200, "msg": "登录成功", "role": user.role, "username": user.username})

    return jsonify({"code": 400, "msg": "用户名或密码错误"})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ================= 3. 核心业务：C端智能对话接口 =================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
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

        # ================= 1. 获取用户农场信息 =================
        farm_info_dict = None
        user_id = session.get('user_id')
        if user_id:
            farm = FarmInfo.query.filter_by(user_id=user_id).first()
            if farm:
                farm_info_dict = {
                    "area": farm.area,
                    "soil_type": farm.soil_type,
                    "main_crop": farm.main_crop,
                    "location": farm.location
                }

        # ================= 2. 意图识别与图谱检索 =================
        intent = graph_rag.extract_intent(user_message)
        kg_data = []
        if intent and intent.get('crop'):
            kg_data = graph_rag.query_neo4j(intent, auto_location=user_location)

        # ================= 3. 调用大模型生成最终回复 =================
        final_reply = graph_rag.generate_final_answer(
            user_message,
            kg_data,
            auto_location=user_location,
            farm_info=farm_info_dict  # 把农场信息传给大模型
        )

        # ================= 4. 记录日志到数据库 =================
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


@app.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"code": 401, "msg": "未登录"})

    try:
        logs = ChatLog.query.filter_by(user_id=user_id).order_by(ChatLog.id.desc()).limit(50).all()
        history_list = [
            {"id": log.id, "query": log.user_query, "reply": log.bot_reply, "location": log.location, "time": log.id}
            for log in logs]
        return jsonify({"code": 200, "data": history_list})
    except Exception as e:
        return jsonify({"code": 500, "msg": "获取历史记录失败"})


# ================= 4. 个人农场与账本接口 =================

@app.route('/profile')
def profile_page():
    """渲染个人主页/农场管理页"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('profile.html')


@app.route('/api/farm/info', methods=['GET', 'POST'])
def farm_info_api():
    """获取或更新土地信息"""
    user_id = session.get('user_id')
    if not user_id: return jsonify({"code": 401, "msg": "未登录"})

    farm = FarmInfo.query.filter_by(user_id=user_id).first()

    if request.method == 'GET':
        if not farm:
            return jsonify({"code": 200, "data": None})
        return jsonify({"code": 200, "data": {
            "area": farm.area, "soil_type": farm.soil_type,
            "main_crop": farm.main_crop, "location": farm.location
        }})

    if request.method == 'POST':
        data = request.json
        if not farm:
            farm = FarmInfo(user_id=user_id)
            db.session.add(farm)

        farm.area = float(data.get('area', 0))
        farm.soil_type = data.get('soil_type', '')
        farm.main_crop = data.get('main_crop', '')
        farm.location = data.get('location', '')

        db.session.commit()
        return jsonify({"code": 200, "msg": "土地信息保存成功"})


@app.route('/api/farm/ledger', methods=['GET', 'POST', 'DELETE'])
def ledger_api():
    """账本的增删查"""
    user_id = session.get('user_id')
    if not user_id: return jsonify({"code": 401, "msg": "未登录"})

    if request.method == 'GET':
        records = Ledger.query.filter_by(user_id=user_id).order_by(Ledger.record_date.desc()).all()
        data = [{"id": r.id, "date": r.record_date, "type": r.type, "category": r.category, "amount": r.amount,
                 "notes": r.notes} for r in records]
        return jsonify({"code": 200, "data": data})

    if request.method == 'POST':
        data = request.json
        new_record = Ledger(
            user_id=user_id,
            record_date=data.get('date'),
            type=data.get('type'),
            category=data.get('category'),
            amount=float(data.get('amount', 0)),
            notes=data.get('notes', '')
        )
        db.session.add(new_record)
        db.session.commit()
        return jsonify({"code": 200, "msg": "记账成功"})

    if request.method == 'DELETE':
        record_id = request.json.get('id')
        record = Ledger.query.filter_by(id=record_id, user_id=user_id).first()
        if record:
            db.session.delete(record)
            db.session.commit()
            return jsonify({"code": 200, "msg": "删除成功"})
        return jsonify({"code": 404, "msg": "记录不存在"})


# ================= 5. 后台管理与数据分析接口 =================

@app.route('/admin')
def admin_page():
    if str(session.get('role', '')).strip() != 'admin':
        return redirect(url_for('login_page'))
    return render_template('admin.html')


@app.route('/api/admin/export/logs', methods=['GET'])
def export_logs():
    if str(session.get('role', '')).strip() != 'admin': return jsonify({"code": 403, "msg": "未授权"}), 403
    try:
        logs = ChatLog.query.order_by(ChatLog.id.desc()).all()
        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output)
        writer.writerow(['日志ID', '用户ID', '咨询问题', '专家回复', '提取意图', '地区', '咨询记录ID'])
        for log in logs:
            writer.writerow([log.id, log.user_id, log.user_query, log.bot_reply,
                             json.dumps(log.extracted_intent, ensure_ascii=False), log.location or '自动定位', log.id])
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=agri_chat_full_report.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response
    except Exception as e:
        return jsonify({"code": 500, "msg": "导出报表失败"})


@app.route('/api/health', methods=['GET'])
def health_check():
    status = {"api": "running", "mysql": "unknown", "neo4j": "connected"}
    try:
        db.session.execute(func.now())
        status["mysql"] = "connected"
    except Exception as e:
        status["mysql"] = f"error: {str(e)}"
    return jsonify(status)


@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    if str(session.get('role', '')).strip() != 'admin': return jsonify({"code": 403, "msg": "未授权"})
    try:
        crop_stats = db.session.query(
            func.json_unquote(func.json_extract(ChatLog.extracted_intent, '$.crop')).label('crop'),
            func.count(ChatLog.id)).group_by('crop').all()
        loc_stats = db.session.query(ChatLog.location, func.count(ChatLog.id)).group_by(ChatLog.location).all()
        return jsonify({
            "crops": [{"name": str(c[0]), "value": c[1]} for c in crop_stats if c[0] and str(c[0]) != 'null'],
            "locations": [{"name": l[0], "value": l[1]} for l in loc_stats if l[0]]
        })
    except Exception as e:
        return jsonify({"crops": [], "locations": []})


@app.route('/api/admin/kg/add', methods=['POST'])
def add_kg_node():
    if str(session.get('role', '')).strip() != 'admin': return jsonify({"code": 403, "msg": "未授权"})
    data = request.json
    success = graph_rag.add_variety_to_kg(data)
    if success: return jsonify({"code": 200, "msg": "新品种已成功写入知识图谱"})
    return jsonify({"code": 500, "msg": "图谱写入失败"})


# ================= 6. 【新增】良种百科大厅接口 =================

@app.route('/encyclopedia')
def encyclopedia_page():
    """渲染良种百科大厅页面"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('encyclopedia.html')


@app.route('/api/encyclopedia/data', methods=['GET'])
def get_encyclopedia_data():
    """获取全库所有品种数据，供给前端瀑布流展示"""
    if 'user_id' not in session:
        return jsonify({"code": 401, "msg": "未登录"})

    try:
        data = graph_rag.get_all_varieties()
        return jsonify({"code": 200, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "msg": "获取百科数据失败"})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)