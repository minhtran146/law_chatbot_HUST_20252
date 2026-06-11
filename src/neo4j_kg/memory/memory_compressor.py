from typing import List, Dict
from memory.entity_extractor import extract_entities


def is_important_turn(user_text: str, assistant_text: str = "") -> bool:
    entities = extract_entities(user_text)
    has_entities = bool(entities)
    has_content = len(assistant_text) > 20 and "[]" not in assistant_text[:50]
    return has_entities or has_content


def compress_turns(turns: List[Dict], max_important: int = 10) -> List[Dict]:
    if not turns:
        return []

    important = []
    noise = []

    for turn in turns:
        if is_important_turn(turn.get("user", ""), turn.get("assistant", "")):
            important.append(turn)
        else:
            noise.append(turn)

    kept = important[-max_important:]
    if noise and kept:
        kept.insert(0, {
            "user": "(...)",
            "assistant": f"(có {len(noise)} lượt hỏi không liên quan đến luật đã được lược bỏ)",
        })

    return kept


def format_compressed_context(turns: List[Dict]) -> str:
    lines = []
    for t in turns:
        user = t.get("user", "")
        assistant = t.get("assistant", "")
        lines.append(f"Người dùng: {user}")
        if assistant:
            lines.append(f"Hệ thống: {assistant}")
    return "\n".join(lines)
