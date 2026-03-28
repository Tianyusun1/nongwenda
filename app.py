from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from neo4j import GraphDatabase

app = Flask(__name__)

# ================= 1. MySQL 关系型数据库配置 =================
# 配置你的 MySQL 连接 (使用 root 和 123456)
# 请确保你已经在本地 MySQL 中提前建好了一个名为 agri_qa 的空数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@127.0.0.1:3306/agri_qa'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化 SQLAlchemy
db = SQLAlchemy(app)

# ================= 2. Neo4j 图数据库配置 =================
# 请核对你的 Neo4j 账号密码（如果 Neo4j 密码也是 123456，请替换下方的密码）
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"  # Neo4j 默认用户名
NEO4J_PASSWORD = "12345678"

# 初始化 Neo4j 驱动
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ================= 3. 健康检查测试接口 =================
@app.route('/api/health', methods=['GET'])
def health_check():
    """用于测试后端和双库连接状态的小接口"""
    status = {"api": "running", "mysql": "unknown", "neo4j": "unknown"}

    # 测试 MySQL 连接
    try:
        with app.app_context():
            db.engine.connect()
            status["mysql"] = "connected"
    except Exception as e:
        status["mysql"] = f"error: {str(e)}"

    # 测试 Neo4j 连接
    try:
        neo4j_driver.verify_connectivity()
        status["neo4j"] = "connected"
    except Exception as e:
        status["neo4j"] = f"error: {str(e)}"

    return jsonify(status)


if __name__ == '__main__':
    # 启动 Flask 服务
    app.run(debug=True, port=5000)