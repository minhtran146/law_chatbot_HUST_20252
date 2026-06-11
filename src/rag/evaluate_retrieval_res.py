import json
import pandas as pd
from tqdm import tqdm
import re
import math 
from rapidfuzz import fuzz
import pandas as pd
from collections import defaultdict
from ranx import Qrels, Run, evaluate

def read_xlsx_file(file_path):
    df = pd.read_excel(file_path)
    return df 

def read_json_file(file_path):
    with open(file_path, 'r',encoding= 'utf-8') as f:
        data = json.load(f)
    return data

def extract_name(name):
    articles = name.split(" Điều ")
    return articles[0]

def extract_content(content):
    content_parts = content.split("\n")
    return content_parts[0]

def map_from_aid_to_article_content():
    res = {}
    with open('data/VLQA/legal_corpus.json', 'r', encoding= 'utf-8') as f:
        legal_corpus = json.load(f)

    for corpus in legal_corpus:
        content = corpus.get('content')
        for article in content:
            aid = article.get('aid')
            content_article = article.get('content_Article')
            res[aid] = content_article
    return res

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    # 3. (Tùy chọn) Loại bỏ dấu câu nếu bạn chỉ muốn so sánh nội dung chữ
    text = re.sub(r'[^\w\s]', '', text)
    # 4. Trim khoảng trắng 2 đầu
    return text.strip()

def check_if_match_fuzzy(content_Article, kg_content):
    score = fuzz.ratio(content_Article, kg_content)
    # print(score)
    return score

def check_if_match(content_Article, kg_content):
    if not isinstance(kg_content, str) or not isinstance(content_Article, str):
        return 0, 0
    
    clean_art = clean_text(content_Article)
    clean_kg = clean_text(kg_content)
    score = check_if_match_fuzzy(clean_art, clean_kg)
    return clean_art == clean_kg, score

def eval_article_retrieve(df, k):
    map_aid_to_content_Article = map_from_aid_to_article_content()
    miss_articles = []
    all_qrels = {}
    all_runs = {}
    rate_list =  []
    for i, sample in df.iterrows():
        top_content = [sample[f'top{i}_content'] for i in range(1, k+1)]
        relevant_law_ids = json.loads(sample['relevant_laws'])
        hit_articles = set()
        miss_article= defaultdict()
        predict_contents = []
        for t_content in top_content:
            predict_aid = map_article_content_to_aid.get(t_content, None)
            predict_contents.append(predict_aid)
            if predict_aid:
                if predict_aid in relevant_law_ids:
                    hit_articles.add(predict_aid)
        if len(hit_articles) == 0:
            print(f'qid not found any relevant aid with qid: {sample["qid"]}, relevant_law_ids: {relevant_law_ids}')
            miss_article['qid'] = sample['qid']
            miss_article['relevant_law_ids'] = relevant_law_ids
            miss_article['question'] = sample['question']
            miss_article['top_contents'] = top_content
            miss_article['predict_contents'] = predict_contents

            miss_articles.append(miss_article)
        
        all_qrels[str(i)] = {str(aid): 1 for aid in relevant_law_ids}
        all_runs[str(i)] = {str(aid): 1.0 / (rank + 1) for rank, aid in enumerate([map_article_content_to_aid.get(t_content, None) for t_content in top_content if map_article_content_to_aid.get(t_content, None) is not None])}
        rate_list.append((relevant_law_ids, hit_articles, len(relevant_law_ids),len(hit_articles)/len(relevant_law_ids)))
    
    # miss_articles to xlsx
    miss_df = pd.DataFrame(miss_articles)
    miss_df.to_excel('data/miss/miss_articles.xlsx', index=False)
    qrels = Qrels(all_qrels)
    run = Run(all_runs)
    final_results = evaluate(qrels, run, metrics=[f"map@{k}"])
    if isinstance(final_results, dict):
        avg_map_score = final_results[f"map@{k}"]
    else:
        avg_map_score = final_results
    
    return rate_list, avg_map_score


if __name__ == "__main__":
    file_name = 'article_retrieval/test.xlsx'
    map_article_content_to_aid = read_json_file('../map_res_v2.json')
    df = read_xlsx_file(file_name)
    k = 10# Map@k
    
    print("\nĐánh giá retrieval article ")
    rate_list, avg_map_score = eval_article_retrieve(df, k)
    print('-'*10)
    print(f'map@{k}:', avg_map_score)
    print(f'precision@{k}: ', sum([rate[3] for rate in rate_list])/len(rate_list))
    print('-'*10)

    d
    count_1_relevant_id = 0
    count_1_retrievable = 0
    count_1_non_retrievable = 0
    count_0 = 0
    count_1 = 0
    count_1_multiple = 0
    count_not_full = 0
    count_miss_multiple = 0
    count_all_question = len(rate_list)
    for relevant_law_ids, hit_articles, num_articles, rate in rate_list:

        if num_articles == 1:
            count_1_relevant_id +=1

        if rate == 0:
            count_0 +=1
            if num_articles == 1:
                count_1_non_retrievable +=1
            if num_articles >1:
                count_miss_multiple +=1
        elif rate == 1:
            count_1 +=1
            if num_articles ==1:
                count_1_retrievable +=1
            if num_articles >1:
                count_1_multiple +=1
        else:
            if num_articles ==1:
                print(f'Error: {rate}')
            count_not_full +=1
            # print(f'Not full: {relevant_law_ids} only hits: {hit_articles}')

    print(f'avg score: {sum([rate[3] for rate in rate_list])/len(rate_list)}')
    print(f"Tong so samples: {count_all_question}")
    print(f"Tong so samples co 1 relevant id: {count_1_relevant_id}")
    print(f"Tong so samples co hon 1 relevant id: {count_all_question - count_1_relevant_id}")
    print(f"so cau 1 dieu retrievable: {count_1_retrievable}")
    print(f"so cau 1 dieu non retrievable: {count_1_non_retrievable}")
    print(f"so samples ko tim thay aid nao: {count_0}")
    print(f"so samples tim thay toan bo aid: {count_1}")
    print(f"so samples tim thay toan bo aid va co hon 1 aid: {count_1_multiple}")
    print(f"so samples tim thay 1 phan aid: {count_not_full}")
    print(f"so samples ko tim thay aid nao va co hon 1 aid: {count_miss_multiple}")
    print(f"ty le hard True: {count_1/count_all_question}")