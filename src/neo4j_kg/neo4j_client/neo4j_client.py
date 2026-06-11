import tqdm

from neo4j import GraphDatabase, Driver
from typing import List, Dict

class Neo4jClient:

    def __init__(self, uri: str, user: str, password: str):
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def search_id(self, id: str):
        with self.driver.session() as session:
            result = session.run("MATCH (n) WHERE n.id = $id RETURN n", id=id)
            record = result.single()
            if record:
                return record["n"]
            else:
                return None
            
    def search_node_by_relation(self, relation: str, current_node_id: str):
        """Tìm kiếm các node có quan hệ cụ thể với node hiện tại"""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n)-[r]->(m) WHERE type(r) = $relation AND n.id = $current_node_id RETURN n, r, m",
                relation=relation,
                related_node_id=current_node_id
            )
            return [record for record in result]

    def search_available_time(self, article_number: str):
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n:Document) WHERE n.name = $article_number RETURN n.id",
                article_number=article_number
            )
            record = result.single()
            document_id = record["n.id"]
            print(f"Document ID: {document_id}")
            # search 1 node with relation document_id "include" that node 
            if document_id:
                result = session.run(
                    "MATCH (n)-[r:include]->(m) WHERE n.id = $document_id RETURN m",
                    document_id=document_id
                )
                record = result.single()
                if record:
                    print(f"Available time: {record['m'].get('available_time')}")
                    return record["m"].get("available_time")
            else :
                print("Document not found.")
                return None
    
    # STT 2, 3, 4
    def search_log_by_document_number_and_index(self, document_number: str, article_index: str):
        tune_document_number = ' ' + document_number
        tune_article_index = "Điều " + article_index + ' '
        with self.driver.session() as session:
            result = session.run(
                # lowercase all string
                "MATCH (n:ArticleLog) WHERE LOWER(n.name) CONTAINS LOWER($tune_document_number) AND LOWER(n.name) CONTAINS LOWER($tune_article_index) RETURN n",
                tune_document_number=tune_document_number,
                tune_article_index=tune_article_index
            )
            record = result.single()

            if record:
                article_log = record["n"]
                article_log_id = article_log.get('id')
                # print(article_log_id)
                available_node = session.run(
                    "MATCH (n:Article)-[r:CÓ_HIỆU_LỰC_THI_HÀNH]->(m:ArticleLog) WHERE m.id = $article_log_id RETURN n",
                    article_log_id=article_log_id
                )   
                available_node_id = available_node.single()['n']['id']
                
                #search all relation from avaliable node
                relations = session.run(
                    "MATCH (n)-[r]->(m) WHERE n.id = $available_node_id RETURN type(r) as relation_type, m",
                    available_node_id=available_node_id
                )
                return [record for record in relations]
            else:
                print("Không tìm thấy log nào phù hợp với số hiệu văn bản và số thứ tự điều.")
                return []

    #STT 8
    def search_articles_by_document_number(self, article_number: str):
        """search list article logs which have relation "include" with document have name is article_number"""
        article_number = article_number.lower()
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n:Document)-[r:include]->(m:ArticleLog) WHERE n.name = $article_number RETURN m",
                article_number=article_number
            )
            # check if result is empty
            if result.peek() is None:
                print("Không tìm thấy văn bản trong cơ sở dữ liệu.")
                return []
            else:
                # search list article which have relation "CÓ_HIỆU_LỰC_THI_HÀNH" with article log
                articles = []
                for record in result:
                    article_log = record["m"]
                    article_log_id = article_log.get("id")
                    # print(f"Article Log ID: {article_log_id}")
                    result_article = session.run(
                        "MATCH (n:Article)-[r:CÓ_HIỆU_LỰC_THI_HÀNH]->(m:ArticleLog) WHERE m.id = $article_log_id RETURN n",
                        article_log_id=article_log_id
                    )
                    for record_article in result_article:
                        articles.append(record_article["n"])
                return articles

    def run_query(self, query: str, params: dict = None):
        with self.driver.session() as session:
            return session.run(query, parameters=params or {}).data()
    
    def merge_nodes(self, tx, label, nodes_batch):
        tx.run(
            f"""
            UNWIND $batch AS row
            MERGE (n:{label} {{id: row['id']}})
            SET n += row
            """,
            batch=nodes_batch
        )

    def create_unique_constraint(self, tx, label):
        tx.run(f"""
        CREATE CONSTRAINT {label}_unique IF NOT EXISTS
        FOR (n:{label}) REQUIRE n.id IS UNIQUE
        """)
    
    def run_unique_constraint(self, label):

        with self.driver.session() as session:
            session.execute_write(self.create_unique_constraint, label)
    
    def create_index(self, tx, label):
        tx.run(f"CREATE INDEX {label}_index IF NOT EXISTS FOR (n:{label}) ON (n.id)")
    
    def run_create_index(self, label):
        with self.driver.session() as session:
            session.execute_write(self.create_index, label)

    def insert_nodes_if_not_exist(self, label: str, nodes: List[Dict]):
        """
        Insert multiple nodes with a specific label if they don't exist.
        Each node should be a dict of properties. Example: {"name": "Alice", "age": 30}
        """
        
        
        with self.driver.session() as session:
            batch_size = 2000
            for i in tqdm.tqdm(range(0, len(nodes), batch_size)):
                batch = nodes[i:i + batch_size]
                session.execute_write(self.merge_nodes, label, batch)
    
    def insert_nodes(self, tx, label, nodes_batch):
        tx.run(
            f"""
            UNWIND $batch AS row
            CREATE (n:{label})
            SET n = row
            """,
            batch=nodes_batch
        )

    def insert_nodes_normal(self, label: str, nodes: List[Dict]):
        """
        Insert multiple nodes with a specific label if they don't exist.
        Each node should be a dict of properties. Example: {"name": "Alice", "age": 30}
        """
        
        self.run_unique_constraint(label)        
        self.run_create_index(label)
        with self.driver.session() as session:
            session.execute_write(self.insert_nodes, label, nodes)


    def batch_include(self, tx, from_label, to_label, rel_type, rel_batch):
        tx.run(
            f"""
            UNWIND $batch AS row
            MATCH (a:{from_label} {{id: row['from_id']}})
            MATCH (b:{to_label} {{id: row['to_id']}})
            MERGE (a)-[r:{rel_type}]->(b)
            """,
            batch=rel_batch
        )
    
    def batch_include_no_exist(self, tx, from_label, to_label, rel_type, rel_batch):
        tx.run(
            f"""
            UNWIND $batch AS row
            MATCH (a:{from_label} {{id: row['from_id']}})
            MATCH (b:{to_label} {{id: row['to_id']}})
            CREATE (a)-[:{rel_type}]->(b)
            """,
            batch=rel_batch
        )


    def batch_relevance(self, tx, from_label, to_label, rel_type, rel_batch):
        tx.run(
            f"""
            UNWIND $batch AS row
            MATCH (a:{from_label} {{id: row['from_id']}})
            MATCH (b:{to_label} {{code: row['to_code']}})
            MERGE (a)-[r:{rel_type}]->(b)
            """,
            batch=rel_batch
        )
    
    def batch_relevance_no_exist(self, tx, from_label, to_label, rel_type, rel_batch):
        tx.run(
            f"""
            UNWIND $batch AS row
            MATCH (a:{from_label} {{id: row['from_id']}})
            MATCH (b:{to_label} {{code: row['to_code']}})
            CREATE (a)-[:{rel_type}]->(b)
            """,
            batch=rel_batch
        )

    def insert_include_batch(self, from_label, to_label, rel_type, relations: list, check_exist=True):
        if check_exist:

            with self.driver.session() as session:
                session.execute_write(self.batch_include, from_label, to_label, rel_type, relations)
        else:
            with self.driver.session() as session:
                session.execute_write(self.batch_include_no_exist, from_label, to_label, rel_type, relations)

    
    def insert_relevance_batch(self, from_label, to_label, rel_type, relations: list, check_exist=True):
        if check_exist:
            with self.driver.session() as session:
                BATCH_SIZE = 2000
                for i in tqdm.tqdm(range(0, len(relations), BATCH_SIZE)):
                    batch = relations[i:i + BATCH_SIZE]
                    # session.write_transaction(run_rel_merge, batch)
                    session.execute_write(self.batch_relevance, from_label, to_label, rel_type, batch)
        else:
            with self.driver.session() as session:
                BATCH_SIZE = 5000
                for i in tqdm.tqdm(range(0, len(relations), BATCH_SIZE)):
                    batch = relations[i:i + BATCH_SIZE]
                    # session.write_transaction(run_rel_merge, batch)
                    session.execute_write(self.batch_relevance_no_exist, from_label, to_label, rel_type, batch)


if __name__ == "__main__":
    # --- Usage example ---
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4j@123"

    client = Neo4jClient(URI, USER, PASSWORD)

    nodes_to_insert = [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25},
        {"id": 3, "name": "Charlie", "age": 35}
    ]

    client.insert_nodes_if_not_exist("Person", nodes_to_insert)

    result = client.run_query("MATCH (n:Person) RETURN n.name AS name, n.age AS age")
    print(result)

    client.close()
