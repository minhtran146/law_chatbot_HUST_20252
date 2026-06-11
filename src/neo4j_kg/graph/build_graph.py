import glob
import os
import tqdm
import json
import sys
sys.path.append("/app/src/rag/")
sys.path.append("/app/src/neo4j_kg/")
print(sys.path)
from collections import defaultdict
 
from neo4j_client.neo4j_client import Neo4jClient
from neo4j_client.relation import Relation
from graph.node import Subject, Title, Part, Chapter, Section, SubSection, Article, ArticleLog
from graph.sample_uuid import generate_unique_id
  

def process_part_chapter_section_subsection(raw_title):
    if raw_title.get("Tiểu mục ID", None) is not None:
        part = Part(name=raw_title["Tên phần"], id=raw_title["Phần ID"], code=raw_title["Phần MAPC"])
        chapter = None
    elif raw_title.get("Mục ID", None) is not None:
        part = None
        chapter = Chapter(name=raw_title["Tên chương"], id=raw_title["Chương ID"], code=raw_title["Chương MAPC"])
    else:
        part = chapter = None
    return part, chapter
 
 
def process_title(raw_title):
    part = chapter = section = subsection = None
    if raw_title.get("Phần ID", None) is not None:
        part = Part(name=raw_title["Tên phần"], id=raw_title["Phần ID"], code=raw_title["Phần MAPC"])
    if raw_title.get("Chương ID", None) is not None:
        chapter = Chapter(name=raw_title["Tên chương"], id=raw_title["Chương ID"], code=raw_title["Chương MAPC"])
    if raw_title.get("Mục ID", None) is not None:
        section = Section(name=raw_title["Tên mục"], id=raw_title["Mục ID"], code=raw_title["Mục MAPC"])
    if raw_title.get("Tiểu mục ID", None) is not None:
        subsection = SubSection(name=raw_title["Tên tiểu mục"], id=raw_title["Tiểu mục ID"], code=raw_title["Tiểu mục MAPC"]) 
    return part, chapter, section, subsection
 
 
def process_articles(list_articles, log_name_id_map):
    return [Article(name=article["Tên điều"],
                    id=article["Điều ID"],
                    code=article["Điều MAPC"],
                    content=article["Nội dung"],
                    relevance_articles=article["Chỉ dẫn"],
                    raw_article_logs=article["Ghi chú"],
                    log_name_id_map=log_name_id_map) for article in list_articles]
 
 
def process_articles_log(list_articles, list_articles_log):
    for article in list_articles:
        raw_article_logs=article["Ghi chú"]
        if isinstance(raw_article_logs, list):
            if len(raw_article_logs):
                print(raw_article_logs)
                assert False
            else:
                continue
        note = raw_article_logs.get("Ghi chú", "")
        metadata = raw_article_logs.get("metadata", [])
        if isinstance(metadata, list):
            for a in metadata:
                if a["Tên điều"] != "":
                    if list_articles_log.get(a["Tên điều"], None):
                        continue
                    else:
                        article_logs_id = generate_unique_id()
                        list_articles_log[a["Tên điều"]] = article_logs_id
    return list_articles_log

def make_subsection(subsection, list_articles):
    subsection.append_articles(list_articles)
    return subsection
 
def make_section(section, subsection, list_articles):
    if subsection:
        if subsection.id not in [e.id for e in section.subsections]:
            subsection = make_subsection(subsection, list_articles)
            section.append_subsections([subsection])
        else:
            idx = [p.id for p in section.subsections].index(subsection.id)
            subsection = make_subsection(section.subsections[idx], list_articles)
            section.subsections[idx] = subsection 
        return section
    if list_articles:
        section.append_articles(list_articles)
    return section
 
 
def make_chapter(chapter, section, subsection, list_articles):
    if section:
        if section.id not in [e.id for e in chapter.sections]:
            section = make_section(section, subsection, list_articles)
            chapter.append_sections([section])
        else:
            idx = [p.id for p in chapter.sections].index(section.id)
            section = make_section(chapter.sections[idx], subsection, list_articles)
            chapter.sections[idx] = section
        return chapter
    
    if subsection:
        if subsection.id not in [e.id for e in chapter.subsections]:
            subsection = make_subsection(subsection, list_articles)
            chapter.append_subsections([subsection])
        else:
            idx = [p.id for p in chapter.subsections].index(subsection.id)
            subsection = make_subsection(chapter.subsections[idx], list_articles)
            chapter.subsections[idx] = subsection 
        return chapter

    if list_articles:
        chapter.append_articles(list_articles)
    return chapter
 

def make_part(part, chapter, section, subsection, list_articles):
    if chapter:
        if chapter.id not in [e.id for e in part.chapters]:
            chapter = make_chapter(chapter, section, subsection, list_articles)
            part.append_chapters([chapter])
        else:
            idx = [p.id for p in part.chapters].index(chapter.id)
            chapter = make_chapter(part.chapters[idx], section, subsection, list_articles)
            part.chapters[idx] = chapter
        return part

    if section:
        if section.id not in [e.id for e in part.sections]:
            section = make_section(section, subsection, list_articles)
            part.append_sections([section])
        else:
            idx = [p.id for p in part.sections].index(section.id)
            section = make_section(part.sections[idx], subsection, list_articles)
            part.sections[idx] = section
        return part
    if subsection:
        if subsection.id not in [e.id for e in part.subsections]:
            subsection = make_subsection(subsection, list_articles)
            part.append_subsections([subsection])
        else:
            idx = [p.id for p in part.subsections].index(subsection.id)
            subsection = make_subsection(part.subsections[idx], list_articles)
            part.subsections[idx] = subsection 
        return part

    if list_articles:
        part.append_articles(list_articles)

    return part
 
def make_title(title, part, chapter, section, subsection, list_articles):
    if part:
        if part.id not in [p.id for p in title.parts]:
            part = make_part(part, chapter, section, subsection, list_articles)
            title.append_parts([part])
        else:
            idx = [p.id for p in title.parts].index(part.id)
            part = make_part(title.parts[idx], chapter, section, subsection, list_articles)
            title.parts[idx] = part
        return title
    if chapter:
        if chapter.id not in [p.id for p in title.chapters]:
            chapter = make_chapter(chapter, section, subsection, list_articles)
            title.append_chapters([chapter])
        else:
            idx = [p.id for p in title.chapters].index(chapter.id)
            chapter = make_chapter(title.chapters[idx], section, subsection, list_articles)
            title.chapters[idx] = chapter
        return title
    return title
 
 
if __name__ == "__main__":
    subjects = []
    all_articles = []
    log_name_id_map = {}
    # with open("data/map_from_article_id_to_doc_name.json", "r", encoding="utf-8") as f:
    #     map_from_article_id_to_doc_name = json.load(f)

        
    for subject_file_path in tqdm.tqdm(glob.glob("data/phap_dien_dataset_45_chu_de/*.json")):
        with open(subject_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for title_raw in data:
            log_name_id_map = process_articles_log(title_raw.get("Các điều", []), log_name_id_map)
    
    print(len(log_name_id_map.keys()))
 
    for subject_file_path in tqdm.tqdm(glob.glob("data/phap_dien_dataset_45_chu_de/*.json")):
        with open(subject_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        subject_tmp = data[0]
        subject = Subject(name=subject_tmp["Tên chủ đề"], id=subject_tmp["Chủ đề ID"], code=subject_tmp["Chủ đề số"])
        titles = []
        for title_raw in data:
            # process de muc
            part, chapter, section, subsection = process_title(title_raw)
            list_articles = process_articles(title_raw.get("Các điều", []), log_name_id_map)
            all_articles.extend(list_articles)
            if title_raw["Đề mục ID"] not in [t.id for t in subject.titles]:
                title = Title(name=title_raw["Tên đề mục"], id=title_raw["Đề mục ID"], code=title_raw["Đề mục số"])
                title = make_title(title, part, chapter, section, subsection, list_articles)
                subject.append_titles([title])
            else:
                idx = [t.id for t in subject.titles].index(title_raw["Đề mục ID"])
                title = make_title(subject.titles[idx], part, chapter, section, subsection, list_articles)
                subject.titles[idx] = title
        # with open(f"structure/{os.path.basename(subject_file_path)[:-5]}.txt", "w", encoding="utf-8") as f:
        #     f.write(subject.structure_represent())
        subjects.append(subject)
    URI = os.getenv("URI", "neo4j://neo4j:7687")
    USER = "neo4j"
    PASSWORD = "12345678"
 
    neo4j_client = Neo4jClient(URI, USER, PASSWORD)
    data_backup = {
        "nodes": [],
        "relations": defaultdict()
    }
    total_chapters = []
    for subject in tqdm.tqdm(subjects):
        data_backup = subject.get_data(data_backup)
        for title in subject.titles:
            total_chapters.extend([c.id for c in title.chapters])
            for part in title.parts:
                total_chapters.extend([c.id for c in part.chapters])

    for article in tqdm.tqdm(all_articles):
        for r_a in article.relevance_articles:
            if r_a.get("ID Điều liên quan", None):
                if data_backup["relations"].get("Article_Article", None) is None:
                    data_backup["relations"]["Article_Article"] = {}
                if data_backup["relations"]["Article_Article"].get(Relation.RELEVANCE, None):
                    if r_a.get("ID Điều liên quan", None):
                        get_ids = [a.id for a in all_articles if a.code == r_a.get("ID Điều liên quan", None)]
                        if len(get_ids):
                            data_backup["relations"]["Article_Article"][Relation.RELEVANCE].append({
                                "from_id": article.id,
                                "to_id": get_ids[0]})
                    
                else:
                    if r_a.get("ID Điều liên quan", None):
                        get_ids = [a.id for a in all_articles if a.code == r_a.get("ID Điều liên quan", None)]
                        if len(get_ids):
                            data_backup["relations"]["Article_Article"][Relation.RELEVANCE] = [{
                                "from_id": article.id,
                                "to_id": get_ids[0]}]

    with open("data/data_backup.json", "w", encoding="utf-8") as f:  
        json.dump(data_backup, f, ensure_ascii=False, indent=4)
    
    # d
    # with open("data/data_backup.json", "r", encoding="utf-8") as f:  
    #     data_backup = json.load(f)



    # d
    print("BEGIN NEW NODES")
    all_nodes_types = ["Subject", "Title", "Part", "Chapter", "Section", "SubSection", "Article", "ArticleLog", "Document"]
    for node_type in tqdm.tqdm(all_nodes_types):
        list_nodes = [n for n in data_backup["nodes"] if n["node_type"] == node_type]
        neo4j_client.insert_nodes_normal(node_type, list_nodes)
    
    print("BEGIN NEW RELATIONS")
    for label_to_label, dict_rels in tqdm.tqdm(data_backup["relations"].items()):
        from_label, target_label = label_to_label.split("_")
        for rel_type, list_rels in dict_rels.items():
            neo4j_client.insert_include_batch(from_label, target_label, rel_type, list_rels, check_exist=False)


    d
    # add document nodes and Document_ArticleLog relations
    with open("data/data_backup.json", "r", encoding="utf-8") as f:  
        data_backup = json.load(f)
                        
    data_backup_document = {
        "nodes": [],
        "relations": defaultdict()
    }
    with open("data/doc_name_to_general_content_t1.json", "r", encoding="utf-8") as f:
        doc_name_to_general_content = json.load(f)
        for k, v in tqdm.tqdm(doc_name_to_general_content.items()): # tqdm
            document_id = generate_unique_id()
            data_backup_document["nodes"].append({
                "node_type": "Document",
                "id": document_id,
                "name": k,})
            for node in data_backup['nodes']:
                if node["node_type"] == "ArticleLog":
                    article_name = node["name"]
                    article_number = article_name.split(" ")[-1].lower()
                    if (article_number == k):
                        if data_backup_document["relations"].get("Document_ArticleLog", None) is None:
                            data_backup_document["relations"]["Document_ArticleLog"] = {}
                        if data_backup_document["relations"]["Document_ArticleLog"].get(Relation.INCLUDE, None) is None:
                            data_backup_document["relations"]["Document_ArticleLog"][Relation.INCLUDE] = []
                        data_backup_document["relations"]["Document_ArticleLog"][Relation.INCLUDE].append({
                            "from_id": document_id,
                            "to_id": node["id"]
                        })

    with open('data/data_backup_document.json', 'w', encoding="utf-8") as f:
        json.dump(data_backup_document, f, ensure_ascii=False, indent=4)
    print("BEGIN DOCUMENT NODES")
    all_nodes_types = ["Document"]
    for node_type in tqdm.tqdm(all_nodes_types):
        list_nodes = [n for n in data_backup_document["nodes"] if n["node_type"] == node_type]
        neo4j_client.insert_nodes_normal(node_type, list_nodes)
    
    print("BEGIN DOCUMENT RELATIONS")
    for label_to_label, dict_rels in tqdm.tqdm(data_backup_document["relations"].items()):
        from_label, target_label = label_to_label.split("_")
        for rel_type, list_rels in dict_rels.items():
            neo4j_client.insert_include_batch(from_label, target_label, rel_type, list_rels, check_exist=False)
    neo4j_client.close()