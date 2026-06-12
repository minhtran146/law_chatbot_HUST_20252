from fastapi import FastAPI
import httpx  # <--- Thêm dòng này
import sys
import re
import os
from openai import OpenAI
import numpy as np
http_client = httpx.Client(verify=False)
sys.path.append("/app/src/rag")
sys.path.append("/app/src/neo4j_kg")
from pydantic import BaseModel
from query import query_article_hybrid
import weaviate
from weaviate.classes.init import AdditionalConfig, Timeout
from neo4j_client.neo4j_client import Neo4jClient
from memory.conversation_memory import ConversationMemory
from memory.entity_memory import EntityMemory
from memory.topic_segmenter import segment_turns, label_segment
from memory.memory_compressor import compress_turns, format_compressed_context

print(sys.path)

COLLECTION_NAME = "bge_clean"
FIELD_TO_BM25 = 'content'
URI = os.getenv("URI", "neo4j://neo4j:7687")
USER = "neo4j"
PASSWORD = "12345678"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

nvidia_client = OpenAI(
    api_key=NVIDIA_API_KEY,
    base_url=NVIDIA_BASE_URL,
    http_client=http_client
)

def encode_query(query: str):
    response = nvidia_client.embeddings.create(
        input=[query],
        model="baai/bge-m3",
        encoding_format="float",
        extra_body={"truncate": "NONE"}
    )
    embedding = response.data[0].embedding
    return np.array(embedding)

#connect to neo4j 
neo4j_client = Neo4jClient(URI, USER, PASSWORD)
print("connected to neo4j")
memory = ConversationMemory(neo4j_client.driver)
entity_memory = EntityMemory(neo4j_client.driver, encode_fn=encode_query)
print("memory ready")
weaviate_client = weaviate.connect_to_local(
        host="weaviate",
        port=8080,
        grpc_port=50051,
        skip_init_checks=True,
    )
print("connected to weaviate")
collection = weaviate_client.collections.get(COLLECTION_NAME)

app = FastAPI()

def get_session(session_id: str) -> str:
    if not session_id:
        session_id = memory.create_session()
    return session_id

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float = 0.7
    session_id: str = ""

@app.post("/query_content")
def query_content(query: QueryRequest):
    session_id = get_session(query.session_id)
    question = query.query.lower()
    top_k = query.top_k
    alpha = query.alpha
    memory.add_message(session_id, "user", query.query)
    entity_memory.store_entities(session_id, query.query)

    turns = memory.get_paired_turns(session_id, limit=20)
    segments = segment_turns(turns)
    compressed = compress_turns(turns, max_important=8)
    conv_context = format_compressed_context(compressed)
    entity_context = entity_memory.build_context(session_id, query.query)

    # segment info
    seg_summary = ""
    if len(segments) > 1:
        current_seg = segments[-1] if segments else None
        if current_seg:
            seg_summary = f"chủ đề hiện tại: {label_segment(current_seg)}"

    context_parts = [p for p in [conv_context, entity_context, seg_summary] if p]
    enriched_query = f"{' | '.join(context_parts)}\n{question}" if context_parts else question

    encoded_query = encode_query(enriched_query)
    result = query_article_hybrid(
        collection,
        enriched_query, 
        encoded_query,
        top_k,
        alpha,
        FIELD_TO_BM25
        )

    final_res = []
    print(result.objects)
    for rank_idx, r in enumerate(result.objects):
        final_res.append({
            "rank": rank_idx + 1,
            "article_node": r.properties

        })
        print(r.properties)
    memory.add_message(session_id, "assistant", str(final_res))
    return {"session_id": session_id, "result": final_res}

# @app.get("/search_available_time")
# def search_available_time(query: QueryRequest):
#     question = query.query.lower()
#     article_number = re.findall(r"(\S+[\/-]\S+([\/-]\S+)*)", question)
#     # print(article_number)
#     available_time = neo4j_client.search_available_time(article_number[0][0].lower()) if article_number else None
#     return {"available_time": available_time}

@app.post("/search_articles_by_document_number")
def search_articles_by_document_number(query: QueryRequest):
    session_id = get_session(query.session_id)
    question = query.query
    memory.add_message(session_id, "user", question)
    entity_memory.store_entities(session_id, question)
    article_number = re.findall(r"(\S+[\/-]\S+([\/-]\S+)*)", question)
    if article_number:
        print(article_number)
        articles = neo4j_client.search_articles_by_document_number(article_number[0][0]) if article_number else []
        memory.add_message(session_id, "assistant", str(articles))
        return {"session_id": session_id, "articles": articles}
    else:
        print("Không thấy số hiệu văn bản trong query.")
        memory.add_message(session_id, "assistant", "Không tìm thấy văn bản")
        return {"session_id": session_id, "articles": []}

@app.post("/search_metadata_and_log_by_document_number_and_index")
def search_metadata_and_log_by_document_number_and_index(query: QueryRequest):
    session_id = get_session(query.session_id)
    question = query.query.lower()
    memory.add_message(session_id, "user", query.query)
    entity_memory.store_entities(session_id, query.query)
    article_number = re.findall(r"(\S+[\/-]\S+([\/-]\S+)*)", question)
    if article_number:
        print(article_number)
        article_index = re.findall(r"điều\s+(\d+)", question) # ví dụ: "điều 1"
        if article_index:
            print(article_index)
            result = neo4j_client.search_log_by_document_number_and_index(article_number[0][0], article_index[0])
            memory.add_message(session_id, "assistant", str(result))
            return {"session_id": session_id, "logs": result}
        else:
            print("Không thấy số thứ tự điều trong query")
            memory.add_message(session_id, "assistant", "Không tìm thấy số thứ tự điều")
            return {"session_id": session_id, "logs": []}
    else:
        print("Không thấy số hiệu văn bản trong query.")
        memory.add_message(session_id, "assistant", "Không tìm thấy văn bản")
        return {"session_id": session_id, "logs": []}