import os
import sys
sys.path.append("C:\\Users\\NhatNT24\\legal_knowledge_graph")
import json
from abc import ABC, abstractmethod
from neo4j_client.neo4j_client import Neo4jClient
from graph.sample_uuid import generate_unique_id
import re
from collections import defaultdict

if __name__== "__main__":
    final_res = {
        'nodes': [],
        'relations': {
            'Document_ArticleLog':{
                "GỒM":[]
            }
        }
    }

    file_path = 'data/grouped_articles.json'
    data_backup_path = 'data_backup.json'
    URI = os.getenv("URI", "neo4j://localhost:7687")
    USER = "neo4j"
    PASSWORD = "12345678"
 
    neo4j_client = Neo4jClient(URI, USER, PASSWORD)

    with open(file_path, 'r', encoding= 'utf-8') as f:
        data = json.load(f)
    with open(data_backup_path, 'r', encoding= 'utf-8') as f:
        data_backup = json.load(f)

# # map from article log name to id
    node_list = data_backup['nodes']
    document_nodes = []
    document_name_set = set()
    doc_name_to_id_map = {}
    from_id_to_id = []

    for node in node_list:
        if node.get('node_type') == "ArticleLog":
            full_log_name = node.get('name')
            doc_name = re.split(r"^Điều \d+ ", full_log_name)[-1]

            if doc_name not in document_name_set:
                doc_id = generate_unique_id()
                document_nodes.append({
                    "node_type": 'Document',
                    "id": doc_id,
                    "name": doc_name
                })
                document_name_set.add(doc_name)
                doc_name_to_id_map[doc_name] = doc_id

            from_id_to_id.append({
                "from_id": doc_name_to_id_map[doc_name],
                "to_id": node.get('id')
            })

    final_res['nodes'].extend(document_nodes)
    final_res['relations']['Document_ArticleLog']["GỒM"].extend(from_id_to_id)

    with open('group_articlelog.json', 'w', encoding= 'utf-8') as f:
        json.dump(final_res, f, ensure_ascii= False, indent= 4)


# insert nodes
    print("insert document node")
    neo4j_client.insert_nodes_normal('Document', document_nodes)
    print("add doc node done")



# insert relations
    print("insert relations")
    neo4j_client.insert_include_batch('Document', 'ArticleLog', "GỒM", from_id_to_id)
    print("insert relations done")