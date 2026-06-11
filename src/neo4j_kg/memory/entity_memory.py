import uuid
from datetime import datetime
from typing import List, Dict, Optional, Callable
from memory.entity_extractor import extract_entities


class EntityMemory:

    def __init__(self, driver, encode_fn: Callable = None):
        self.driver = driver
        self.encode_fn = encode_fn
        self._ensure_schema()

    def _ensure_schema(self):
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT session_entity_id_unique IF NOT EXISTS "
                "FOR (e:SessionEntity) REQUIRE e.id IS UNIQUE"
            )
            session.run(
                "CREATE INDEX session_entity_value IF NOT EXISTS "
                "FOR (e:SessionEntity) ON (e.value)"
            )

    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        if self.encode_fn is None:
            return None
        try:
            vec = self.encode_fn(text)
            if hasattr(vec, 'tolist'):
                return vec.tolist()
            if isinstance(vec, (list, tuple)):
                return list(vec)
            return None
        except Exception:
            return None

    def store_entities(self, session_id: str, query: str):
        entities = extract_entities(query)
        if not entities:
            return
        now = datetime.utcnow().isoformat()
        with self.driver.session() as session:
            for ent in entities:
                existing = session.run(
                    "MATCH (e:SessionEntity {session_id: $session_id, "
                    "entity_type: $entity_type, value: $value}) "
                    "WHERE e.status IS NULL OR e.status <> 'superseded' "
                    "RETURN e.id AS eid",
                    session_id=session_id,
                    entity_type=ent["type"],
                    value=ent["value"],
                ).single()

                if existing:
                    session.run(
                        "MATCH (e:SessionEntity {id: $eid}) "
                        "SET e.updated_at = $updated_at",
                        eid=existing["eid"], updated_at=now,
                    )
                    continue

                embedding = self._compute_embedding(ent["value"])
                entity_id = str(uuid.uuid4())

                props = {
                    "id": entity_id,
                    "session_id": session_id,
                    "entity_type": ent["type"],
                    "value": ent["value"],
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                }
                if embedding is not None:
                    props["embedding"] = embedding

                session.run(
                    "MATCH (s:Session {id: $session_id}) "
                    "CREATE (e:SessionEntity $props) "
                    "CREATE (s)-[:HAS_ENTITY]->(e) "
                    "WITH e "
                    "RETURN e.id",
                    session_id=session_id,
                    props=props,
                )

                self._link_to_kg(entity_id, ent)

    def _link_to_kg(self, entity_id: str, entity: Dict):
        with self.driver.session() as session:
            if entity["type"] == "document_number":
                val = entity["value"].lower()
                matches = session.run(
                    "MATCH (d:Document) WHERE LOWER(d.name) CONTAINS $val "
                    "RETURN d.id AS target_id, 'Document' AS target_label",
                    val=val,
                ).single()
                if matches:
                    session.run(
                        "MATCH (e:SessionEntity {id: $eid}) "
                        "MATCH (target:Document {id: $tid}) "
                        "MERGE (e)-[:REFERS_TO]->(target)",
                        eid=entity_id, tid=matches["target_id"],
                    )

            elif entity["type"] == "article_index":
                num = entity["value"].split()[-1]
                matches = session.run(
                    "MATCH (a:Article) WHERE a.name CONTAINS $num "
                    "RETURN a.id AS target_id, 'Article' AS target_label",
                    num=num,
                )
                for m in matches:
                    session.run(
                        "MATCH (e:SessionEntity {id: $eid}) "
                        "MATCH (target:Article {id: $tid}) "
                        "MERGE (e)-[:REFERS_TO]->(target)",
                        eid=entity_id, tid=m["target_id"],
                    )

    def get_session_entities(self, session_id: str) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (s:Session {id: $session_id})-[:HAS_ENTITY]->(e:SessionEntity) "
                "WHERE e.status IS NULL OR e.status <> 'superseded' "
                "RETURN e.entity_type AS entity_type, e.value AS value, "
                "e.created_at AS created_at "
                "ORDER BY e.created_at ASC",
                session_id=session_id,
            )
            seen = set()
            unique = []
            for record in result:
                key = (record["entity_type"], record["value"])
                if key not in seen:
                    seen.add(key)
                    unique.append({
                        "type": record["entity_type"],
                        "value": record["value"],
                    })
            return unique

    def find_cross_session_entities(self, entity_value: str) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (e:SessionEntity) WHERE e.value = $value "
                "AND (e.status IS NULL OR e.status <> 'superseded') "
                "RETURN DISTINCT e.value AS value, e.entity_type AS entity_type, "
                "COUNT(DISTINCT e.session_id) AS session_count",
                value=entity_value,
            )
            return [{"value": r["value"], "type": r["entity_type"],
                     "sessions": r["session_count"]} for r in result]

    def build_context(self, session_id: str, current_query: str) -> str:
        current_entities = extract_entities(current_query)
        current_docs = {e["value"].lower() for e in current_entities if e["type"] == "document_number"}
        current_articles = {e["value"].lower() for e in current_entities if e["type"] == "article_index"}

        past_entities = self.get_session_entities(session_id)
        parts = []
        for e in past_entities:
            val_lower = e["value"].lower()
            if e["type"] == "document_number" and val_lower not in current_docs:
                cross = self.find_cross_session_entities(e["value"])
                label = e["value"]
                if cross and cross[0]["sessions"] > 1:
                    label += f" (đã hỏi ở {cross[0]['sessions']} phiên)"
                parts.append(("doc", label))
            elif e["type"] == "article_index" and val_lower not in current_articles:
                cross = self.find_cross_session_entities(e["value"])
                label = e["value"]
                if cross and cross[0]["sessions"] > 1:
                    label += f" (đã hỏi ở {cross[0]['sessions']} phiên)"
                parts.append(("article", label))

        seen_labels = set()
        unique_parts = []
        for kind, label in parts:
            if label not in seen_labels:
                seen_labels.add(label)
                unique_parts.append((kind, label))

        doc_parts = [l for k, l in unique_parts if k == "doc"]
        article_parts = [l for k, l in unique_parts if k == "article"]
        out = []
        if doc_parts:
            out.append("văn bản đang được hỏi: " + ", ".join(doc_parts))
        if article_parts:
            out.append("điều luật đang được hỏi: " + ", ".join(article_parts))
        return "; ".join(out)

    def search_similar_entities(self, query_vec: List[float], top_k: int = 3) -> List[Dict]:
        if not query_vec:
            return []
        with self.driver.session() as session:
            result = session.run(
                "MATCH (e:SessionEntity) WHERE e.embedding IS NOT NULL "
                "AND (e.status IS NULL OR e.status <> 'superseded') "
                "RETURN e.value AS value, e.entity_type AS type, "
                "e.embedding AS embedding, e.session_id AS session_id "
            )
            scored = []
            for record in result:
                emb = record["embedding"]
                if not emb:
                    continue
                sim = sum(a * b for a, b in zip(query_vec, emb))
                scored.append((sim, {
                    "value": record["value"],
                    "type": record["type"],
                    "session_id": record["session_id"],
                }))
            scored.sort(key=lambda x: -x[0])
            return [item[1] for item in scored[:top_k]]

    def supersede_entity(self, entity_id: str, new_entity_id: str):
        with self.driver.session() as session:
            session.run(
                "MATCH (e:SessionEntity {id: $eid}) "
                "SET e.status = 'superseded', e.superseded_by = $new_id "
                "SET e.updated_at = $now",
                eid=entity_id, new_id=new_entity_id,
                now=datetime.utcnow().isoformat(),
            )

    def delete_session(self, session_id: str):
        with self.driver.session() as session:
            session.run(
                "MATCH (s:Session {id: $session_id}) "
                "OPTIONAL MATCH (s)-[:HAS_ENTITY]->(e:SessionEntity) "
                "DETACH DELETE e",
                session_id=session_id,
            )
