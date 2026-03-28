import json
from neo4j import GraphDatabase
# 确保你的 local_model.py 文件名正确且在同一目录下
from local_model import qwen_brain

# ================= 1. Neo4j 连接配置 =================
# 密码已根据你的要求改为 12345678
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = "12345678"

neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PWD))


# ================= 2. 核心逻辑函数 =================

def extract_intent(user_query):
    """【意图识别】让本地 Qwen 提取结构化 JSON"""
    system_prompt = (
        "你是一个农业意图提取助手。请只输出JSON：{'crop':作物,'location':地区,'disease':病害,'feature':特性}。"
        "如果没有提到某项则填null。不要输出任何 Markdown 标记或解释，只输出纯 JSON 字符串。"
    )

    try:
        # 调用 local_model.py 中的 qwen_brain 实例
        response_text = qwen_brain.chat(system_prompt, user_query)

        # 1.5B 模型有时会吐出 ```json ... ```，这里做彻底清理
        clean_json = response_text.replace("```json", "").replace("```", "").strip()

        # 将字符串转为 Python 字典
        intent_dict = json.loads(clean_json)

        # 统一处理：将字符串类型的 "null" 转为真正的 None
        for key in intent_dict:
            if intent_dict[key] == "null" or intent_dict[key] == "":
                intent_dict[key] = None
        return intent_dict
    except Exception as e:
        print(f"❌ 意图解析失败。模型原始输出: {response_text if 'response_text' in locals() else 'None'}")
        return None


def query_neo4j(intent):
    """【知识检索】使用模糊匹配查询图数据库"""
    if not intent or not intent.get('crop'):
        return None

    # 升级后的 Cypher：使用 CONTAINS 实现模糊匹配（如：河南 匹配 河南省）
    cypher = """
    MATCH (v:Variety)-[:BELONGS_TO]->(c:Crop)
    WHERE c.name CONTAINS $crop

    // 地点过滤逻辑：如果用户没提地点，则匹配所有地点
    OPTIONAL MATCH (v)-[:SUITABLE_FOR]->(l:Location)
    WITH v, c, l, $location AS loc_query
    WHERE loc_query IS NULL OR l.name CONTAINS loc_query

    // 获取抗病性和抗逆性数据
    OPTIONAL MATCH (v)-[:RESISTANT_TO]->(p:PestDisease)
    OPTIONAL MATCH (v)-[:TOLERANT_TO]->(s:AbioticStress)

    RETURN v.name AS 品种, 
           v.yield AS 亩产, 
           v.approval_number AS 审定号,
           collect(DISTINCT p.name) AS 抗病害,
           collect(DISTINCT s.name) AS 耐受特性
    ORDER BY v.yield DESC LIMIT 3
    """

    with neo4j_driver.session() as session:
        # 提取参数
        params = {
            "crop": intent.get('crop'),
            "location": intent.get('location')
        }

        result = session.run(cypher, params)
        records = [dict(record) for record in result]
        return records


def generate_final_answer(user_query, kg_data):
    """【答案生成】将检索到的真实数据喂给 Qwen 生成回复"""
    if not kg_data:
        return "抱歉，在我的农业知识库中暂时没有找到完全符合您要求的品种建议。建议咨询当地种子站。"

    system_prompt = "你是一个亲切且专业的农业专家。请根据提供的知识图谱真实数据来回答农户问题，语气要接地气。"

    # 将图谱数据转为易读的字符串
    data_info = json.dumps(kg_data, ensure_ascii=False, indent=2)
    input_content = f"农户提问：{user_query}\n\n后台检索到的真实品种数据：\n{data_info}\n\n请根据以上数据给出推荐："

    return qwen_brain.chat(system_prompt, input_content)


# ================= 3. 运行主循环 =================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🌾 离线农业百科问答系统 (Qwen-1.5B + Neo4j)")
    print("输入 'quit' 退出系统")
    print("=" * 50)

    try:
        while True:
            user_input = input("\n👤 农户提问: ").strip()
            if not user_input: continue
            if user_input.lower() == 'quit': break

            # 1. 识别意图
            intent = extract_intent(user_input)
            if not intent or not intent.get('crop'):
                print("🤖 没太听懂您的需求，您是想问哪种作物（如：玉米、小麦）？")
                continue

            print(f"DEBUG -> 意图提取: {intent}")

            # 2. 检索图谱
            print(f"🔍 正在检索知识图谱...")
            results = query_neo4j(intent)

            # 3. 汇总回答
            print("🤖 专家分析中...")
            answer = generate_final_answer(user_input, results)

            print(f"\n🌟 专家建议：\n{answer}")

    except KeyboardInterrupt:
        print("\n程序已停止。")
    finally:
        neo4j_driver.close()