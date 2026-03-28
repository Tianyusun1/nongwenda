import json
from neo4j import GraphDatabase
from local_model import qwen_brain

# ================= 1. Neo4j 连接配置 =================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = "12345678"

# 初始化单例驱动
try:
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PWD))
    print("✅ Neo4j 图数据库连接就绪 (graph_rag 模块)")
except Exception as e:
    print(f"❌ Neo4j 连接失败: {e}")


# ================= 2. GraphRAG 核心处理流水线 (C端对话用) =================

def extract_intent(user_query):
    """【第一步：意图识别】让 Qwen 提取结构化 JSON 意图"""
    system_prompt = (
        "你是一个农业意图提取助手。请只输出JSON：{'crop':作物,'location':地区,'disease':病害,'feature':特性}。"
        "如果没有提到某项则填null。不要输出任何 Markdown 标记或解释，只输出纯 JSON 字符串。"
    )
    try:
        response_text = qwen_brain.chat(system_prompt, user_query)
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        intent_dict = json.loads(clean_json)

        for key in intent_dict:
            if intent_dict[key] == "null" or intent_dict[key] == "":
                intent_dict[key] = None
        return intent_dict
    except Exception as e:
        print(f"❌ 意图解析失败: {e}")
        return None

def query_neo4j(intent, auto_location=None):
    """【第二步：图谱检索】双向模糊匹配 + 智能降级"""
    if not intent or not intent.get('crop'):
        return None

    search_location = intent.get('location') or auto_location

    cypher = """
    MATCH (v:Variety)-[:BELONGS_TO]->(c:Crop)
    WHERE c.name CONTAINS $crop

    OPTIONAL MATCH (v)-[:SUITABLE_FOR]->(l:Location)
    WITH v, c, l, $location AS loc_query
    WHERE loc_query IS NULL OR l.name CONTAINS loc_query OR loc_query CONTAINS l.name

    OPTIONAL MATCH (v)-[:RESISTANT_TO]->(p:PestDisease)
    OPTIONAL MATCH (v)-[:TOLERANT_TO]->(s:AbioticStress)

    RETURN v.name AS 品种, 
           v.yield AS 亩产, 
           v.approval_number AS 审定号,
           collect(DISTINCT p.name) AS 抗病害,
           collect(DISTINCT s.name) AS 耐受特性
    ORDER BY v.yield DESC LIMIT 3
    """

    try:
        with neo4j_driver.session() as session:
            params = {"crop": intent.get('crop'), "location": search_location}
            result = session.run(cypher, params)
            records = [dict(record) for record in result]

            if not records and search_location:
                print(f"⚠️ 在 {search_location} 未找到 {intent.get('crop')}，降级查询全国范围...")
                params["location"] = None
                result_fallback = session.run(cypher, params)
                records = [dict(record) for record_fallback in result_fallback]

            return records
    except Exception as e:
        print(f"❌ 图谱查询出错: {e}")
        return []

def generate_final_answer(user_query, kg_data, auto_location=None):
    """【第三步：答案生成】大模型兜底与图谱融合 (修复了覆盖问题)"""
    loc_context = f"（注：系统检测到用户当前可能在 {auto_location}）\n" if auto_location else ""

    if not kg_data:
        print("⚠️ 知识图谱无特定品种数据，启用 Qwen 本地知识库兜底！")
        system_prompt = (
            "你是一个亲切且专业的农业专家。系统知识库中暂时没有匹配的良种数据，"
            "但请你运用你的通用农业知识，详细解答农户的问题（如种植技术、通用选种建议）。"
            "语气要接地气、通俗易懂，多给一些实用的操作步骤。"
        )
        input_content = f"{loc_context}农户提问：{user_query}\n\n请直接给出你的专业农业建议："
        try:
            return qwen_brain.chat(system_prompt, input_content)
        except Exception as e:
            return "抱歉，我的大脑暂时有点短路，请稍后再试。"

    # 有图谱数据时的处理
    system_prompt = (
        "你是一个亲切且专业的农业专家。请主要根据提供的知识图谱真实数据来推荐品种。"
        "同时，如果用户问到了【怎么种】、【如何管理】等技术问题，请结合你的通用农业知识给予指导。"
        "要求：\n"
        "1. 语气接地气、通俗易懂。\n"
        "2. 清晰地列出推荐品种的优势。\n"
        "3. 不要捏造图谱中没有的品种参数。"
    )

    data_info = json.dumps(kg_data, ensure_ascii=False, indent=2)
    input_content = f"{loc_context}农户提问：{user_query}\n\n后台检索到的真实品种数据：\n{data_info}\n\n请提供解答和种植建议："

    try:
        return qwen_brain.chat(system_prompt, input_content)
    except Exception as e:
        return "抱歉，我的语言中枢似乎短路了，请稍后再试。"


# ================= 3. 后台图谱管理接口 (B端录入/删除用) =================

def add_variety_to_kg(data):
    """
    接收来自后台表单的数据，写入 Neo4j
    data 示例: {"crop": "小麦", "variety": "新麦2026", "yield": 600, "approval": "国审123", "locations": ["河南", "河北"], "resistances": ["白粉病", "抗倒伏"]}
    """
    cypher = """
    MERGE (c:Crop {name: $crop})
    MERGE (v:Variety {name: $variety})
    SET v.yield = toFloat($yield), v.approval_number = $approval
    MERGE (v)-[:BELONGS_TO]->(c)

    WITH v
    UNWIND $locations AS loc
    MERGE (l:Location {name: loc})
    MERGE (v)-[:SUITABLE_FOR]->(l)

    WITH v
    UNWIND $resistances AS res
    MERGE (r:PestDisease {name: res}) // 简单起见，统一放入抗性节点
    MERGE (v)-[:RESISTANT_TO]->(r)
    """
    try:
        with neo4j_driver.session() as session:
            session.run(cypher,
                        crop=data.get('crop'),
                        variety=data.get('variety'),
                        yield_=data.get('yield', 0),
                        approval=data.get('approval', '未知'),
                        locations=data.get('locations', []),
                        resistances=data.get('resistances', []))
        return True
    except Exception as e:
        print(f"❌ 写入图谱失败: {e}")
        return False