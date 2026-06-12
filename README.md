## Cấu trúc

```
btc/
├── data/                      # Thư mục lưu trữ dữ liệu (mount từ volumes của Weaviate và Neo4j)
│   ├── backups
│   ├── neo4j_backup
│   └── weaviate_backups
├── python_run/
│   ├── Dockerfile             # Dockerfile để build môi trường chạy Python
│   ├── docker-compose.yml     # Build image Python (dùng riêng lẻ)
│   └── requirements.txt       # Các dependencies của dự án Python
├── src/
│   ├── fastapi/
│   │   └── main_api.py        # Server FastAPI và các endpoints
│   ├── gradio_app.py          # Gradio UI (tích hợp Groq LLM để sinh câu trả lời tự nhiên)
│   ├── models/                # Cache mô hình SentenceTransformer (BAAI/bge-m3)
│   ├── neo4j_kg/
│   │   ├── graph/             # Xây dựng Knowledge Graph luật pháp
│   │   ├── neo4j_client/      # Kết nối và truy vấn Neo4j
│   │   └── memory/            # Hệ thống bộ nhớ hội thoại
│   │       ├── conversation_memory.py  # Buffer memory (lưu raw messages)
│   │       ├── entity_extractor.py     # Trích xuất thực thể pháp lý bằng regex
│   │       ├── entity_memory.py        # Entity graph memory (Mem0g-style)
│   │       ├── topic_segmenter.py      # Phân đoạn hội thoại theo chủ đề
│   │       └── memory_compressor.py    # Nén extractive loại bỏ nhiễu
│   ├── rag/                   # Logic RAG, schema Weaviate, pipeline query & import
│   └── model.py               # Tải mô hình SentenceTransformer (BAAI/bge-m3)
├── docker-compose.yml         # Orchestrator: Neo4j + Weaviate + FastAPI + Gradio
├── .env                       # GROQ_API_KEY, NVIDIA_API_KEY
└── README.md
```

## Hướng dẫn khởi chạy

### Yêu cầu hệ thống
- Cài đặt **Docker** và **Docker Compose**.
- Cổng `8080`, `50051` dành cho Weaviate, cổng `7474`, `7687` dành cho Neo4j, cổng `8002` dùng cho FastAPI, cổng `7860` cho Gradio UI.
- **Groq API key** (tại https://console.groq.com) và **NVIDIA API key** (tại https://build.nvidia.com) — đặt trong file `.env`:
  ```
  GROQ_API_KEY=gsk_...
  NVIDIA_API_KEY=nvapi-...
  ```

Tạo network trong Docker:
```bash
docker network create law_net
```

### Khởi chạy toàn bộ hệ thống

```bash
docker-compose up -d
```

### Import dữ liệu từ backup (nếu có sẵn file dump)

#### Neo4j — Load dump:
```bash
docker run --rm -v "$PWD/neo4j/data:/data" -v "$PWD/data/backups/neo4j_backup:/backups" neo4j:latest neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
```

#### Weaviate — Restore backup:
```bash
# Cách 1: qua API (nếu scheduler hoạt động)
curl -X POST http://localhost:8080/v1/backups/filesystem/weaviate-backup/restore -H "Content-Type: application/json" -d '{}'

# Cách 2: copy thủ công shard files (dùng khi API restore fail)
docker cp data/backups/weaviate_backups/weaviate-backup/. weaviate:/var/lib/weaviate/bge_clean/
docker restart weaviate
```

#### Khởi động lại FastAPI + Gradio (sau khi có dữ liệu):
```bash
docker restart fastapi gradio
```

### Import dữ liệu từ đầu (nếu không có backup)

```bash
python src/rag/create_schema.py
python src/rag/import_data.py
python src/neo4j_kg/graph/build_graph.py
```

## Endpoints

### `POST /query_content`
Tìm kiếm hybrid (BM25 + vector search) trên các điều luật. Hai chế độ search:

- **Câu hỏi có entity** (số văn bản, điều khoản): BM25 trên `note_content` + hybrid trên `[content, note_content, article_name]`, gộp kết quả (ưu tiên exact match).
- **Câu hỏi không entity** (follow-up): enrich query với entity context từ các lượt trước trong cùng session.

**Payload:**
```json
{
    "query": "Điều khiển xe máy sau khi uống rượu bia bị phạt gì?",
    "session_id": ""
}
```
- `session_id`: để trống → tạo session mới; gửi UUID nhận từ response trước → nối tiếp hội thoại.

**Response:**
```json
{
    "session_id": "uuid...",
    "result": [{"rank": 1, "article_node": {...}}, ...]
}
```

### `GET /session_history`
Lấy lịch sử hội thoại của một session từ Neo4j.
```
GET /session_history?session_id=<uuid>
```
```json
{
    "session_id": "uuid...",
    "history": [{"role": "user", "content": "..."}, ...]
}
```

### `POST /search_articles_by_document_number`
Truy xuất các điều luật thuộc một văn bản (Neo4j).

### `POST /search_metadata_and_log_by_document_number_and_index`
Tra cứu lịch sử sửa đổi của một điều khoản.

## Gradio UI

Truy cập `http://localhost:7860` để dùng giao diện chat. Hỗ trợ đa phiên (tạo/xoá/chuyển phiên qua dropdown).

- UI gọi FastAPI lấy context RAG, sau đó dùng Groq LLM (llama-3.3-70b) để sinh câu trả lời tự nhiên.
- `top_k: 10` — LLM nhận 10 articles làm context.
- Prompt LLM bao gồm **lịch sử hội thoại** của phiên hiện tại để hỗ trợ follow-up.
- Khi chuyển phiên: nếu in-memory không có history, tự động load từ Neo4j qua `/session_history`.
- **Lưu ý:** sau khi refresh trang, state Gradio bị reset (session mapping name→UUID mất). Lịch sử vẫn còn trong Neo4j nhưng cần load lại bằng session_id cũ (hiện chưa hỗ trợ tự động).

## Hệ thống bộ nhớ hội thoại

### 1. Conversation Memory (buffer)
- Lưu raw messages (user + assistant) dưới dạng node `Session` → `Message` trong Neo4j.
- Persistent: đóng session, mở lại sau — lịch sử vẫn còn.

### 2. Entity Memory (Mem0g-style)
- Regex trích xuất thực thể pháp lý từ câu hỏi: số văn bản (`24/2020/TT-BCA`), số điều (`Điều 1`), số khoản, loại văn bản.
- Lưu node `SessionEntity` trong Neo4j với các field: `value`, `entity_type`, `embedding` (vector), `status` (active/superseded).
- Tự động link `SessionEntity` → `Document`/`Article` node có sẵn trong KG qua relation `REFERS_TO`.
- Cross-session: khi build context, phát hiện entity đã xuất hiện ở session khác → gắn nhãn `(đã hỏi ở N phiên)`.
- Update/Delete: entity trùng được cập nhật thời gian; entity cũ có thể đánh dấu `superseded`.
- Similarity search: dùng embedding vector (NVIDIA BAAI/bge-m3) để tìm entity tương tự qua các session.

### 3. Topic Segmenter
- Heuristics phát hiện thay đổi chủ đề dựa trên entities (số văn bản, số điều thay đổi → cắt segment mới).
- Segment hiện tại được đưa vào context dưới dạng `chủ đề hiện tại: ...`.

### 4. Memory Compressor
- Phân loại turns: *important* (có entities hoặc kết quả) vs *noise*.
- Noise được gom thành 1 dòng tóm tắt; important giữ tối đa 8 turns gần nhất.
- Giảm nhiễu trong context window.

### Luồng xử lý request (`query_content`)
```
User JSON
  → get_session() (tạo mới / kiểm tra session tồn tại trong Neo4j)
  → ConversationMemory: lưu user message vào Neo4j
  → EntityMemory.store_entities() — extract entities + lưu SessionEntity
  → Nếu query KHÔNG có entity pháp lý:
      entity_context = EntityMemory.build_context() (entity từ lượt trước)
      search_query = "{entity_context}\n{question}"
  → Nếu query CÓ entity (số văn bản / điều):
      search_query = question
  → NVIDIA encode → Weaviate hybrid search (BM25: content+note_content+article_name)
  → Nếu query có entity: search bổ sung BM25 trên note_content
      → gộp kết quả (ưu tiên exact match từ note_content)
  → ConversationMemory: lưu response
  → return {session_id, result}

Gradio UI:
  → format_context() — lấy content từ các article_node
  → build_prompt() — thêm lịch sử hội thoại + context + câu hỏi
  → Groq LLM (llama-3.3-70b) → trả lời tự nhiên
```

## Backup

### Neo4j

**Dump:**
```bash
docker run --rm --volumes-from my_neo4j -v $(pwd)/data/backups/neo4j_backup:/backups neo4j:latest neo4j-admin database dump neo4j --to-path=/backups
```

**Load:**
```bash
docker run --rm -v "$PWD/neo4j/data:/data" -v "$PWD/data/backups/neo4j_backup:/backups" neo4j:latest neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
```

### Weaviate

**Dump:**
```bash
curl -X POST http://localhost:8080/v1/backups/filesystem -H "Content-Type: application/json" -d '{
  "id": "weaviate-backup"
}'
```

**Load:**
```bash
curl -X POST http://localhost:8080/v1/backups/filesystem/weaviate-backup/restore -H "Content-Type: application/json" -d '{}'
```
