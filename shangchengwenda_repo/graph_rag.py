import json
import re
from neo4j import GraphDatabase
from local_model import qwen_brain

neo4j_driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678'))

def clean_json_string(raw):
    m = re.search(r'(\{.*\})', raw, re.DOTALL)
    return m.group(1) if m else raw

def extract_intent(user_query):
    prompt = (
        '你是电商客服意图提取器，只输出JSON：'
        "{'intent_type':意图,'product_name':商品,'order_no':订单号,'issue_type':问题类型,'urgency':紧急程度}。"
        '未知字段填null，严禁输出解释。'
    )
    try:
        text = qwen_brain.chat(prompt, user_query)
        return json.loads(clean_json_string(text))
    except Exception:
        return {'intent_type': None, 'product_name': None, 'order_no': None, 'issue_type': None, 'urgency': None}

def query_kg(intent):
    product_name = intent.get('product_name') if intent else None
    if not product_name:
        return []
    cypher = """
    MATCH (p:Product)
    WHERE p.name CONTAINS $name
    OPTIONAL MATCH (p)-[:HAS_POLICY]->(po:Policy)
    OPTIONAL MATCH (p)-[:HAS_FAQ]->(f:FAQ)
    RETURN p.name as product, p.price as price, p.stock as stock,
           collect(DISTINCT po.content) as policies,
           collect(DISTINCT f.question + '：' + f.answer) as faqs
    LIMIT 3
    """
    try:
        with neo4j_driver.session() as session:
            rows = [dict(r) for r in session.run(cypher, {'name': product_name})]
            return rows
    except Exception:
        return []

def generate_final_answer(user_query, intent, kg_data, order_info=None):
    intent_text = json.dumps(intent or {}, ensure_ascii=False)
    kg_text = json.dumps(kg_data or [], ensure_ascii=False, indent=2)
    order_text = json.dumps(order_info or {}, ensure_ascii=False)

    no_kg_guidance = (
        '若知识图谱为空，请明确告知“暂未检索到商品图谱信息”，'
        '然后给出通用客服建议（下单、物流、退换货、人工客服路径），并提示用户补充订单号或商品名。'
    )
    system_prompt = (
        '你是电商智能客服（Qwen1.5），语气专业、简洁、可执行。'
        '优先依据知识图谱和订单信息，不得编造。'
        '涉及退款/赔付时给出流程建议并提示人工审核。'
        + no_kg_guidance
    )
    user_content = (
        f'用户问题：{user_query}\n'
        f'识别意图：{intent_text}\n'
        f'订单信息：{order_text}\n'
        f'知识图谱结果：{kg_text}\n'
    )
    try:
        return qwen_brain.chat(system_prompt, user_content)
    except Exception:
        return '抱歉，客服助手暂时不可用。建议您稍后重试，或联系人工客服。'
