
import weaviate
import os
import json
import re
import ssl
from collections import defaultdict
from tqdm import tqdm
from weaviate.classes.query import MetadataQuery, Filter
from weaviate.collections.classes.internal import QueryReturn
from weaviate.classes.init import AdditionalConfig, Timeout
from dotenv import load_dotenv
load_dotenv()
# os.environ["HTTP_PROXY"] = "http://10.36.252.45:8080"
# os.environ["HTTPS_PROXY"] = "http://10.36.252.45:8080"
# os.environ['TRANSFORMERS_OFFLINE'] = '1'
# os.environ['HF_HUB_OFFLINE'] = '1'
# os.environ['no_proxy'] = '127.0.0.1,localhost'
ssl._create_default_https_context = ssl._create_unverified_context


def read_sample_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def client_init(api_key, base_url):
    from openai import OpenAI
    client = OpenAI(api_key = api_key, 
                    base_url = base_url)
    return client


def query_article_bm25(article, query: str, top_k: int = 3):
    
    results = article.query.bm25(
        query=query, 
        query_properties=["content"],
        limit=top_k, 
        return_metadata=MetadataQuery(
            score=True,  
            explain_score=True, 
        ),
    )
    return results

def query_article_hybrid(article, query: str, q_vec, top_k: int = 3, alpha = 0.45, query_properties = None):
    if query_properties is None:
        query_properties = ["content", "note_content", "article_name"]
    results = article.query.hybrid(
        query=query, 
        vector=q_vec.tolist(),
        query_properties=query_properties,
        alpha=alpha,
        limit=top_k, 
        return_metadata=MetadataQuery(score=True),
    )
    return results


def encode_questions(model, questions,weaviate_collection_name = None, batch_size=64):
    print('-'*20)
    print(f"Đang encode {len(questions)} câu hỏi...")
    all_vectors = model.encode(questions, batch_size=batch_size, convert_to_numpy=True, show_progress_bar=True)
    return all_vectors
    

def query(collection, data, all_vectors, alpha, top_k = 20, field_to_bm25_search = "embedding_field"):
    with open('data/VLQA/map_aid_to_note.json', 'r', encoding= 'utf-8') as f:
        map_aid_to_note = json.load(f)
    final_res = []
    for i, sample in enumerate(tqdm(data, desc = "Retrieving")):
        question = sample['question'].lower()
        q_vec = all_vectors[i]

        # Truy vấn
        query_res = query_article_hybrid(collection, question, q_vec, top_k, alpha, field_to_bm25_search)

        per_res = defaultdict()
        per_res['qid'] = sample['qid']
        per_res['question'] = question
        per_res['relevant_laws'] = sample['relevant_laws']
        per_res['relevant_notes'] = [map_aid_to_note.get(str(aid)) for aid in sample['relevant_laws']]
        
        # Lưu kết quả top 10
        for rank_idx, r in enumerate(query_res.objects):
            rank = rank_idx + 1
            per_res[f'top{rank}_article_id'] = r.properties.get('article_id')
            # per_res[f'top{rank}_article_name'] = r.properties.get('article_name')
            per_res[f'top{rank}_note'] = r.properties.get('instruct')
            per_res[f'top{rank}_content'] = r.properties.get('content')
            # per_res[f'top{rank}_score'] = r.metadata.score
            
        per_res['answer'] = sample['answer']
        final_res.append(per_res)
    return final_res

# if __name__ == "__main__":
#     alpha = 0.7
#     output_path = 'article_retrieval/test_sj.xlsx'
#     weaviate_collection_name = "centroid_subject_name_w_general_content_wo_content"
#     print(f'Sử dụng collection: {weaviate_collection_name}')
#     question_file_path = 'data/VLQA/filtered_train_after_map_aid.json'
#     field_to_bm25_search = "embedding_field"
    # filter_level = 'closest'

#model and client init 
    # model = SentenceTransformer(
    #     'BAAI/bge-m3',
    #     cache_folder = 'models'
    #     trust_remote_code=True,
    # )
    # client = weaviate.connect_to_local(
    #     host="127.0.0.1",
    #     port=8080,
    #     grpc_port=50051,
    #     skip_init_checks=True,
    #     additional_config=AdditionalConfig(
    #     timeout=Timeout(init=300, query=600, insert=1200)  # Values in seconds
    # )
    # )
    
    # collection = client.collections.get(weaviate_collection_name)
    # data = read_sample_file(question_file_path)
    # all_questions = [sample['question'] for sample in data]
    # all_vectors = encode_questions(model, all_questions, weaviate_collection_name ,batch_size=64)
    # Retrieve
        # print(f"Đang truy vấn")
    # with open('../map_aid_to_added_info.json', 'r', encoding= 'utf-8') as f:
    #     map_aid_to_added_info = json.load(f)
    # final_res =  (collection, data, all_vectors, alpha, 5, field_to_bm25_search)
    # final_res = query_all_parent_info(collection, data, all_vectors,
    #                                   map_aid_to_added_info, alpha, top_k=50, 
    #                                   field_to_bm25_search=field_to_bm25_search)
    # final_res = query(collection, data, all_vectors, alpha, 
    #                 top_k=10, field_to_bm25_search=field_to_bm25_search)
    # final_res = query_w_fixed_stage_1(collection, data, all_vectors, filter_level= filter_level,
    #                                  top_k=20, alpha=alpha, field_to_bm25_search=field_to_bm25_search)

# Save Results
    # print("Lưu kết quả vào file Excel...")
    # df = pd.DataFrame(final_res)
    # os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # df.to_excel(output_path, index=False)
    # print(f"Đã lưu kết quả vào {output_path}")

    # client.close()