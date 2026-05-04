# shangchengwenda

独立于原项目的新商城问答系统（不破坏原仓库业务）。

## 核心功能
- 智能问答（Qwen1.5，本地模型）
- 用户注册登录（MySQL）
- 商品查询
- 订单查询
- 聊天历史
- 知识图谱检索 + 未命中兜底回答

## 启动
```bash
export SC_DATABASE_URI='mysql+pymysql://root:123456@127.0.0.1:3306/shangcheng_qa'
export QWEN_MODEL_PATH='/path/to/qwen1.5'
cd shangchengwenda
python app.py
```

服务默认启动在 `http://127.0.0.1:5050`。
