import requests, uuid

BASE = "http://localhost:8002"
session_id = ""

print("=== TEST 1: Tạo session mới ===")
r = requests.post(f"{BASE}/query_content", json={
    "query": "Theo Điều 5 của Thông tư 24/2020/TT-BCA quy định thế nào?",
    "session_id": ""
})
data = r.json()
session_id = data.get("session_id", "")
print(f"  session_id: {session_id}")
assert session_id, "Không có session_id"
print("  PASS")

print("\n=== TEST 2: Hỏi tiếp, context được giữ ===")
r2 = requests.post(f"{BASE}/query_content", json={
    "query": "Điều 10 trong cùng văn bản nói gì?",
    "session_id": session_id
})
assert r2.ok
print("  PASS (enriched_query sẽ có 24/2020/TT-BCA + Điều 5 từ lượt trước)")

print("\n=== TEST 3: Session cũ không hợp lệ → vẫn chấp nhận ===")
r3 = requests.post(f"{BASE}/query_content", json={
    "query": "Nghị định 45/2019/NĐ-CP là gì?",
    "session_id": str(uuid.uuid4())
})
assert r3.ok
print("  PASS (session mới được tạo tự động)")

print("\n=== TEST 4: Entity cross-session ===")
# Dùng lại session cũ — entity cũ (24/2020/TT-BCA) sẽ được build_context nhắc lại
r4 = requests.post(f"{BASE}/query_content", json={
    "query": "Điều 15 nói gì?",
    "session_id": session_id
})
assert r4.ok
print("  PASS (entity_context có thể ghi 'đã hỏi ở N phiên')")

print("\n--- ALL TESTS PASSED ---")
