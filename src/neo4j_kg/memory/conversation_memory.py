import uuid
from datetime import datetime
from typing import List, Dict, Optional


class ConversationMemory:

    def __init__(self, driver):
        self.driver = driver
        self._ensure_schema()

    def _ensure_schema(self):
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT session_id_unique IF NOT EXISTS "
                "FOR (s:Session) REQUIRE s.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT message_id_unique IF NOT EXISTS "
                "FOR (m:Message) REQUIRE m.id IS UNIQUE"
            )
            session.run(
                "CREATE INDEX session_created_at IF NOT EXISTS "
                "FOR (s:Session) ON (s.created_at)"
            )

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.driver.session() as session:
            session.run(
                "CREATE (s:Session {id: $id, created_at: $created_at})",
                id=session_id, created_at=now
            )
        return session_id

    def add_message(self, session_id: str, role: str, content: str):
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.driver.session() as session:
            session.run(
                "MATCH (s:Session {id: $session_id}) "
                "CREATE (m:Message {id: $msg_id, role: $role, content: $content, timestamp: $timestamp}) "
                "CREATE (s)-[:HAS_MESSAGE]->(m)",
                session_id=session_id,
                msg_id=msg_id,
                role=role,
                content=content,
                timestamp=now,
            )

    def get_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (s:Session {id: $session_id})-[:HAS_MESSAGE]->(m:Message) "
                "RETURN m.role AS role, m.content AS content, m.timestamp AS timestamp "
                "ORDER BY m.timestamp ASC "
                "LIMIT $limit",
                session_id=session_id,
                limit=limit,
            )
            return [{"role": record["role"], "content": record["content"]}
                    for record in result]

    def format_context(self, session_id: str, limit: int = 3) -> str:
        history = self.get_history(session_id, limit)
        if not history:
            return ""
        lines = []
        for msg in history:
            prefix = "Người dùng" if msg["role"] == "user" else "Hệ thống"
            lines.append(f"{prefix}: {msg['content']}")
        return "\n".join(lines)

    def get_paired_turns(self, session_id: str, limit: int = 20) -> List[Dict]:
        msgs = self.get_history(session_id, limit * 2)
        turns = []
        i = 0
        while i < len(msgs) - 1:
            if msgs[i]["role"] == "user" and msgs[i + 1]["role"] == "assistant":
                turns.append({
                    "user": msgs[i]["content"],
                    "assistant": msgs[i + 1]["content"],
                })
                i += 2
            else:
                turns.append({"user": msgs[i]["content"], "assistant": ""})
                i += 1
        return turns

    def delete_session(self, session_id: str):
        with self.driver.session() as session:
            session.run(
                "MATCH (s:Session {id: $session_id}) OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message) "
                "DETACH DELETE s, m",
                session_id=session_id,
            )
