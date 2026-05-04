# shangchengwenda_repo

独立仓库版本的商城问答系统（与原任务仓库解耦）。

## 核心功能
- 智能问答（Qwen1.5，本地模型）
- 用户注册登录（MySQL）
- 商品查询
- 商城主页与商品详情页
- 订单查询
- 商家上架/下架商品
- 商家发货、顾客确认收货
- 管理员审核商家入驻
- 聊天历史
- 知识图谱检索 + 未命中兜底回答

## 启动
```bash
export SC_DATABASE_URI='mysql+pymysql://root:123456@127.0.0.1:3306/shangcheng_qa'
export QWEN_MODEL_PATH='/path/to/qwen1.5'
cd shangchengwenda_repo
python app.py
```

服务默认启动在 `http://127.0.0.1:5050`。
