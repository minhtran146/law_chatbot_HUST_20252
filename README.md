## Cấu trúc

```
btc/
├── data/                      # Thư mục lưu trữ dữ liệu (mount từ volumes của Weaviate và Neo4j)
│   ├── backups
│   ├── neo4j_backup
│   └── weaviate_backups
├── python_run/
│   ├── Dockerfile             # Dockerfile để build môi trường chạy Python
│   ├── docker-compose.yml     # Khởi chạy container chạy mã nguồn Python (FastAPI/RAG)
│   └── requirements.txt       # Các dependencies của dự án Python
├── src/
│   ├── fastapi/
│   │   └── main_api.py        # Server FastAPI và các endpoints
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
│   └── model.py               # Tải mô hình BAAI/bge-m3
├── docker-compose.yml         # Khởi chạy Weaviate + Neo4j
└── README.md
```

## Hướng dẫn khởi chạy

### Yêu cầu hệ thống
- Docker và Docker Compose
- Cổng `8080`, `50051` (Weaviate), `7474`, `7687` (Neo4j), `8002` (FastAPI)

```bash
docker network create law_net
```

### Khởi chạy database

```bash
docker-compose up -d
```

Import dữ liệu (nếu chạy lần đầu):
```bash
python src/rag/create_schema.py
python src/rag/import_data.py
python src/neo4j_kg/graph/build_graph.py
```

### Khởi chạy API

```bash
cd python_run
docker-compose up -d
docker exec -it run_python uvicorn src.fastapi.main_api:app --host 0.0.0.0 --port 8002
```

## Endpoints

### `POST /query_content`
Tìm kiếm hybrid (BM25 + vector search) trên các điều luật.

**Payload:**
```json
{
    "query": "Điều khiển xe máy sau khi uống rượu bia bị phạt gì?",
    "session_id": ""
}
```
- `session_id`: để trống để tạo session mới, hoặc gửi lại session_id cũ để nối tiếp hội thoại. Dữ liệu được lưu persistent trong Neo4j nên có thể quay lại bất kỳ lúc nào.

**Response:**
```json
{
    "session_id": "uuid...",
    "result": [...]
}
```

### `POST /search_articles_by_document_number`
Truy xuất các điều luật thuộc một văn bản (Neo4j).

### `POST /search_metadata_and_log_by_document_number_and_index`
Tra cứu lịch sử sửa đổi của một điều khoản.

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
- Similarity search: dùng embedding vector để tìm entity tương tự qua các session.

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
  → get_session() (tạo mới/dùng session_id có sẵn)
  → ConversationMemory: lưu user message vào Neo4j
  → EntityMemory.store_entities()
      - regex extract entities
      - compute embedding (SentenceTransformer)
      - lưu/merge SessionEntity node
      - link REFERS_TO → Document/Article trong KG
  → MemoryCompressor: nén turns cũ (giữ important, gom noise)
  → TopicSegmenter: phát hiện segment hiện tại
  → build_context: entity context (session + cross-session)
  → enrich query: "[compressed context] | [entity context] | [segment info]
                   câu hỏi gốc"
  → SentenceTransformer encode → Weaviate hybrid search
  → ConversationMemory: lưu response
  → return {session_id, result}
```
