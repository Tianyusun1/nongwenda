import json
from neo4j import GraphDatabase


class RealGraphImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def import_data(self, json_file_path):
        with open(json_file_path, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)

        print(f"📦 正在注入 {len(batch_data)} 条农业名种数据...")

        cypher_query = """
        UNWIND $batch AS data
        MERGE (c:Crop {name: data.crop_name})
        MERGE (v:Variety {name: data.variety_name})
        SET v.approval_number = data.approval_number, v.yield = data.yield, v.growth_cycle = data.growth_cycle
        MERGE (v)-[:BELONGS_TO]->(c)
        MERGE (i:Institution {name: data.institution})
        MERGE (v)-[:DEVELOPED_BY]->(i)

        WITH data, v
        UNWIND data.locations AS loc
        MERGE (l:Location {name: loc})
        MERGE (v)-[:SUITABLE_FOR]->(l)

        WITH data, v
        UNWIND data.climates AS cli
        MERGE (cl:Climate {name: cli})
        MERGE (v)-[:REQUIRES_CLIMATE]->(cl)

        WITH data, v
        UNWIND data.pest_resistances AS pest
        MERGE (p:PestDisease {name: pest.name})
        MERGE (v)-[r:RESISTANT_TO]->(p)
        SET r.level = pest.level

        WITH data, v
        UNWIND data.abiotic_stress AS stress
        MERGE (s:AbioticStress {name: stress.name})
        MERGE (v)-[r:TOLERANT_TO]->(s)
        SET r.level = stress.level
        """

        with self.driver.session() as session:
            # 执行批量注入
            session.run(cypher_query, batch=batch_data)

        print("🎉 真实数据入库完成！这才是值得信赖的知识图谱！")


if __name__ == "__main__":
    # ⚠️ 确保密码正确
    importer = RealGraphImporter("bolt://localhost:7687", "neo4j", "12345678")
    importer.import_data('nongchanpin.json')
    importer.driver.close()

# neo4j.bat console