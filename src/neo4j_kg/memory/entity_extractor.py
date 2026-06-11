import re
from typing import List, Dict


LEGAL_PATTERNS = {
    "document_number": re.compile(
        r"(\d{2,3}/?\d{0,4}/(?:TT|NĐ|QĐ|CT|LT|BLĐTBXH|BVHTTDL|BNNPTNT|BGTVT|BCT|BTTTT|BCA|BQP|BN|BYT|BGDĐT|BTNMT|BVHTTDL|BTP|BTC|BKHĐT|BVHTTDL|UBND|TTg)\b(?:\S*))",
        re.IGNORECASE,
    ),
    "article_index": re.compile(
        r"(?:điều|điều|điêù)\s+(\d+)", re.IGNORECASE
    ),
    "clause_index": re.compile(
        r"(?:khoản|khoản)\s+(\d+)", re.IGNORECASE
    ),
    "document_type_keyword": re.compile(
        r"(thông tư|nghị định|quyết định|luật|pháp lệnh|nghị quyết|chỉ thị|thông tư liên tịch|hướng dẫn)",
        re.IGNORECASE,
    ),
}


def extract_entities(text: str) -> List[Dict]:
    entities = []
    for entity_type, pattern in LEGAL_PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            entities.append({
                "type": entity_type,
                "value": value,
            })
    return entities


def build_entity_context(entities: List[Dict]) -> str:
    if not entities:
        return ""
    parts = []
    has_doc = any(e["type"] == "document_number" for e in entities)
    has_article = any(e["type"] == "article_index" for e in entities)
    if has_doc:
        doc_vals = [e["value"] for e in entities if e["type"] == "document_number"]
        parts.append(f"văn bản: {', '.join(doc_vals)}")
    if has_article:
        art_vals = [e["value"] for e in entities if e["type"] == "article_index"]
        parts.append(f"điều: {', '.join(art_vals)}")
    return "; ".join(parts) if parts else ""
