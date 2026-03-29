import json
import re
from neo4j import GraphDatabase
from local_model import qwen_brain

# ================= 1. Neo4j 连接配置 =================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = "12345678"

try:
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PWD))
    print("✅ Neo4j 图数据库连接就绪 (graph_rag 模块)")
except Exception as e:
    print(f"❌ Neo4j 连接失败: {e}")


# ================= 2. 核心辅助函数 =================

def clean_json_string(raw_str):
    """强力提取 JSON 字符串，防止模型输出 Markdown 代码块或多余文字"""
    try:
        # 使用正则匹配最外层的 { ... }
        match = re.search(r'(\{.*\})', raw_str, re.DOTALL)
        if match:
            return match.group(1)
        return raw_str
    except Exception:
        return raw_str


# ================= 3. GraphRAG 核心处理流水线 =================

def extract_intent(user_query):
    """【意图识别】增加强校验逻辑"""
    system_prompt = (
        "你是一个农业意图提取助手。请只输出JSON：{'crop':作物,'location':地区,'disease':病害,'feature':特性}。"
        "如果没有提到某项则填null。严禁输出任何解释性文字。"
    )
    try:
        response_text = qwen_brain.chat(system_prompt, user_query)
        json_str = clean_json_string(response_text)
        intent_dict = json.loads(json_str)

        # 统一清理 null 字符串
        for key in intent_dict:
            if str(intent_dict[key]).lower() in ["null", "none", ""]:
                intent_dict[key] = None
        return intent_dict
    except Exception as e:
        print(f"❌ 意图解析失败: {e}")
        return {"crop": None, "location": None, "disease": None, "feature": None}


def query_neo4j(intent, auto_location=None):
    """【图谱检索】模糊匹配与降级查询"""
    if not intent or not intent.get('crop'):
        return []

    search_location = intent.get('location') or auto_location

    cypher = """
    MATCH (v:Variety)-[:BELONGS_TO]->(c:Crop)
    WHERE c.name CONTAINS $crop OR v.name CONTAINS $crop

    OPTIONAL MATCH (v)-[:SUITABLE_FOR]->(l:Location)
    WITH v, c, l, $location AS loc_query
    WHERE loc_query IS NULL 
       OR l.name CONTAINS loc_query 
       OR loc_query CONTAINS l.name

    OPTIONAL MATCH (v)-[r:RESISTANT_TO|TOLERANT_TO]->(trait)

    RETURN DISTINCT v.name AS variety, 
           v.yield AS yield, 
           v.approval_number AS approval,
           collect(DISTINCT trait.name) AS resistances
    ORDER BY v.yield DESC LIMIT 3
    """

    try:
        with neo4j_driver.session() as session:
            params = {"crop": intent.get('crop'), "location": search_location}
            result = session.run(cypher, params)
            records = [dict(record) for record in result]

            # 降级查询：如果在指定地区找不到，尝试全国范围
            if not records and search_location:
                print(f"⚠️ 在 {search_location} 未找到 {intent.get('crop')}，尝试全国范围...")
                params["location"] = None
                result_fb = session.run(cypher, params)
                records = [dict(rec) for rec in result_fb]

            return records
    except Exception as e:
        print(f"❌ 图谱查询出错: {e}")
        return []


def generate_final_answer(user_query, kg_data, auto_location=None, farm_info=None, ledger_stats=None):
    """
    【答案生成】带有 Context-Aware（上下文感知）的大模型兜底与图谱融合
    【重大升级】新增 ledger_stats 字典，根据农户的真实盈亏情况动态调整策略！
    """
    # 1. 构建用户背景上下文
    context_parts = []
    if auto_location:
        context_parts.append(f"当前自动定位：{auto_location}")

    # 解析并拼接农场信息
    if farm_info:
        farm_details = []
        if farm_info.get('area') and float(farm_info.get('area')) > 0:
            farm_details.append(f"{farm_info.get('area')}亩")
        if farm_info.get('soil_type'):
            farm_details.append(f"{farm_info.get('soil_type')}地")
        if farm_info.get('main_crop'):
            farm_details.append(f"主种{farm_info.get('main_crop')}")

        if farm_details:
            context_parts.append(f"农场硬件条件：{'，'.join(farm_details)}")

    # ================= 新增：解析账本盈亏情况 =================
    if ledger_stats:
        total_income = ledger_stats.get('total_income', 0)
        total_expense = ledger_stats.get('total_expense', 0)
        profit = total_income - total_expense

        # 将财务数据翻译成大模型容易理解的经营状况
        financial_context = f"财务状况：总收入{total_income}元，总支出{total_expense}元，当前净利润{profit}元。"
        if profit < 0:
            financial_context += "（注意：目前处于亏损状态，资金紧张）"
        elif profit > 10000:
            financial_context += "（注意：目前盈利良好，资金充裕）"

        context_parts.append(financial_context)
    # ========================================================

    loc_context = f"【系统提供给你的农户背景情报：{'; '.join(context_parts)}】\n" if context_parts else ""

    # 2. 编写具备商业思维的 System Prompt
    financial_guidance = (
        "【重要策略指导】：请务必分析提示中的『财务状况』。"
        "1. 如果农户处于【亏损或资金紧张】，请安抚情绪，优先推荐管理粗放、抗逆性强、试错成本低、能省化肥农药的高性价比方案；"
        "2. 如果农户【盈利良好】，请夸奖他的经营，并推荐高产上限更高、或经济附加值更高的优良品种；"
        "3. 在回复中，要像老朋友一样自然地提及他的账本盈亏情况和农场硬件，体现出你是他的专属经营管家。"
    )

    if not kg_data:
        system_prompt = (
                "你是一个不仅懂农业，还懂经营的农业专家大管家。系统知识库中暂无对应品种数据。"
                "请结合通用农业知识解答用户问题。\n" + financial_guidance
        )
        input_content = f"{loc_context}农户问题：{user_query}"
    else:
        system_prompt = (
                "你是一个不仅懂农业，还懂经营的农业专家大管家。请根据提供的真实知识图谱数据进行推荐。"
                "要求：\n1. 严禁捏造图谱以外的品种参数；\n2. 给出实际的种植建议。\n" + financial_guidance
        )
        data_info = json.dumps(kg_data, ensure_ascii=False, indent=2)
        input_content = f"{loc_context}农户问题：{user_query}\n\n知识图谱检索到的真实品种数据：\n{data_info}"

    try:
        return qwen_brain.chat(system_prompt, input_content)
    except Exception:
        return "抱歉，由于网络原因，我现在无法提供详细解答。"


# ================= 4. 百科全书与图谱管理接口 =================

def get_all_varieties():
    """
    【新增】获取全库所有品种信息，用于良种百科页面展示
    按作物分类，并按亩产降序排列
    """
    cypher = """
    MATCH (v:Variety)-[:BELONGS_TO]->(c:Crop)
    OPTIONAL MATCH (v)-[:SUITABLE_FOR]->(l:Location)
    OPTIONAL MATCH (v)-[r:RESISTANT_TO|TOLERANT_TO]->(t:Trait)
    RETURN c.name AS crop, 
           v.name AS variety, 
           v.yield AS yield, 
           v.approval_number AS approval,
           collect(DISTINCT l.name) AS locations,
           collect(DISTINCT t.name) AS resistances
    ORDER BY c.name, v.yield DESC
    """
    try:
        with neo4j_driver.session() as session:
            result = session.run(cypher)
            return [dict(record) for record in result]
    except Exception as e:
        print(f"❌ 获取百科全库数据失败: {e}")
        return []


def add_variety_to_kg(data):
    """
    【修正】：确保写入的节点类型与查询逻辑一致
    """
    cypher = """
    MERGE (c:Crop {name: $crop})
    MERGE (v:Variety {name: $variety})
    SET v.yield = toFloat($yield_val), v.approval_number = $approval
    MERGE (v)-[:BELONGS_TO]->(c)

    WITH v
    UNWIND $locations AS loc
    MERGE (l:Location {name: loc})
    MERGE (v)-[:SUITABLE_FOR]->(l)

    WITH v
    UNWIND $resistances AS res
    MERGE (t:Trait {name: res}) 
    MERGE (v)-[:RESISTANT_TO]->(t)
    """
    try:
        with neo4j_driver.session() as session:
            session.run(cypher,
                        crop=data.get('crop'),
                        variety=data.get('variety'),
                        yield_val=data.get('yield', 0),
                        approval=data.get('approval', '未知'),
                        locations=data.get('locations', []),
                        resistances=data.get('resistances', []))
        return True
    except Exception as e:
        print(f"❌ 写入图谱失败: {e}")
        return False