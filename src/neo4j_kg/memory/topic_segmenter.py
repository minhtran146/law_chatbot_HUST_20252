from typing import List, Dict, Tuple
from memory.entity_extractor import extract_entities


def segment_turns(turns: List[Dict]) -> List[Dict]:
    if not turns:
        return []

    segments = []
    current_docs = set()
    current_articles = set()
    segment_start = 0

    for i, turn in enumerate(turns):
        user_text = turn.get("user", "")
        entities = extract_entities(user_text)
        doc_entities = {e["value"].lower() for e in entities if e["type"] == "document_number"}
        art_entities = {e["value"].lower() for e in entities if e["type"] == "article_index"}

        has_topic_info = bool(doc_entities or art_entities)

        if has_topic_info:
            new_docs = doc_entities - current_docs
            new_arts = art_entities - current_articles

            if (new_docs or new_arts) and i > segment_start:
                segments.append({
                    "start": segment_start,
                    "end": i - 1,
                    "document": list(current_docs),
                    "article": list(current_articles),
                })
                segment_start = i
                current_docs = doc_entities
                current_articles = art_entities
            else:
                current_docs.update(doc_entities)
                current_articles.update(art_entities)
        else:
            if i - segment_start >= 3 and not has_topic_info:
                if i > segment_start:
                    segments.append({
                        "start": segment_start,
                        "end": i - 1,
                        "document": list(current_docs),
                        "article": list(current_articles),
                    })
                segment_start = i
                current_docs = set()
                current_articles = set()

    if segment_start < len(turns):
        segments.append({
            "start": segment_start,
            "end": len(turns) - 1,
            "document": list(current_docs),
            "article": list(current_articles),
        })

    return segments


def label_segment(segment: Dict) -> str:
    parts = []
    if segment["document"]:
        parts.append(", ".join(segment["document"]))
    if segment["article"]:
        parts.append(", ".join(segment["article"]))
    return " | ".join(parts) if parts else "chung"
