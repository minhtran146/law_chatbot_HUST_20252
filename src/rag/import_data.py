import weaviate
import json
from collections import defaultdict
from glob import glob
from tqdm import tqdm
import os
import torch
from sentence_transformers import SentenceTransformer
import ssl

os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

ssl._create_default_https_context = ssl._create_unverified_context
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'


os.environ['no_proxy'] = '127.0.0.1,localhost'
os.environ['NO_PROXY'] = '127.0.0.1,localhost'

def get_data_w_metadata(filename):
    data_res = []
    with open(filename, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    for section in file_data:
        ten_chu_de = section.get("Tên chủ đề", "") # title
        ten_de_muc = section.get("Tên đề mục", "") # Subject
        ten_phan = section.get("Tên phần", "") #part
        ten_chuong = section.get("Tên chương", "") #chapter
        ten_muc = section.get("Tên mục", "")# section
        ten_tieu_muc = section.get("Tên tiểu mục", "") # subsection

        intro_text = ''
        if ten_chu_de:
            intro_text += f'Trong chủ đề {ten_chu_de}, '
        if ten_de_muc:
            intro_text += f'đề mục {ten_de_muc}, '
        if ten_phan:
            intro_text += f'{ten_phan}, '
        if ten_chuong:
            intro_text += f'{ten_chuong}, '
        if ten_muc:
            intro_text += f'{ten_muc}, '
        if ten_tieu_muc:
            intro_text += f'{ten_tieu_muc}, '

        rules = section.get("Các điều", "")
        if len(rules):
            for rule in rules:
                import_data = defaultdict()
                #id
                article_id = rule.get("Điều ID", "")
                if len(article_id) == 0:
                    print("id len = 0")
                import_data["article_id"] = article_id

                #name = Tên điều + Nội dung ghi chú
                article_name = rule.get("Tên điều", "")
                note = rule.get("Ghi chú", {})
                if len(note):
                    note_content = note['Ghi chú']
                name = article_name+ ', ' + note_content
                import_data["name"] = name

                #content
                content = rule.get("Nội dung","")
                import_data["content"] = content

                import_data['name'] = intro_text + import_data['name']  + ' có nội dung như sau ' + content
                
                #origin name
                import_data['origin_name'] = article_name

                #instruct
                import_data['instruct'] = note_content

                data_res.append(import_data)
    return data_res

def import_to_weaviate(collection, batch_size_import, file_paths, embedding_field, model, batch_size_encode=64, embedding_from_local = True):
    """ Có 2 lựa chọn là embedding từ local hoặc từ colab"""
    with collection.batch.fixed_size(
            batch_size=batch_size_import,        
    ) as batch:
        if embedding_from_local: # nếu embedding từ máy local
            for file_path in tqdm(file_paths, desc="Processing files"):
                # res_data = get_data(file_path)
                res_data = get_data_w_metadata(file_path)
                
                if len(res_data) == 0:
                    continue
                texts_to_encode = [d[embedding_field] for d in res_data] # Chọn trường embedding
                # 2. Encode bằng SentenceTransformer
                # GTE trả về một numpy array trực tiếp, không cần truy cập ['dense_vecs']
                # Tham số convert_to_numpy=True để dễ dàng xử lý
                embeddings = model.encode(
                    texts_to_encode, 
                    batch_size=batch_size_encode, 
                    convert_to_numpy=True
                )['dense_vecs']
                for i, data in enumerate(res_data):
                    batch.add_object(
                        properties={
                            "article_id": data['article_id'],
                            "name": data['name'],
                            "content": data['content'],
                            "origin_name": data['origin_name'],
                            "instruct": data['instruct']
                        },
                        vector=embeddings[i].tolist() if embedding_from_local else map_from_article_id_to_embedding[data['article_id']]
                    )
        else: # nếu embedding từ colab
            with open('data/data_for_local_bge_clean.json', 'r', encoding='utf-8') as f:
                data_for_gte = json.load(f)
                map_from_article_id_to_embedding = {}
                for item in data_for_gte:
                    map_from_article_id_to_embedding[item['article_id']] = item['vector']

            for i, data in enumerate(tqdm(data_for_gte)):
                batch.add_object(
                    properties={
                        "article_id": data['article_id'],
                        "mapc": data['Điều MAPC'],
                        "article_name": data['article_name'],
                        "note_content": data['note_content'],
                        "content": data['content']
                    },
                    vector=embeddings[i].tolist() if embedding_from_local else map_from_article_id_to_embedding[data['article_id']]
                )
        
    if collection.batch.failed_objects:
        print(f"Số lượng object bị lỗi: {len(collection.batch.failed_objects)}")
        print(collection.batch.failed_objects[0])


if __name__ == "__main__":

    model = 1

    client = weaviate.connect_to_local(
        host="weaviate",
        port=8080,
        grpc_port=50051,
        skip_init_checks=True
    )
    
    file_paths = glob('../../data/phap_dien_dataset_45_chu_de/*.json')
    subject_titles_parts = client.collections.get("bge_clean")
    batch_size_import = 64
    batch_size_encode = 64
    embedding_field = "embedding_field"
    try:
        import_to_weaviate(
            collection=subject_titles_parts,
            batch_size_import=batch_size_import, # Số lượng object import trong một batch
            file_paths=file_paths,
            embedding_field=embedding_field, # Trường dùng để embedding
            model=model,
            batch_size_encode=batch_size_encode, # Số lượng câu được encode trong một batch
            embedding_from_local=False
        )

    finally:
        client.close()
        