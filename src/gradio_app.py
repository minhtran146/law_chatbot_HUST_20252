import gradio as gr
import groq
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8002")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

client = groq.Groq(api_key=GROQ_API_KEY)


def format_context(result):
    if not result or "result" not in result:
        return "Không tìm thấy kết quả phù hợp."

    articles = result["result"]
    if not articles:
        return "Không tìm thấy kết quả phù hợp."

    lines = []
    for item in articles:
        props = item.get("article_node", {})
        title = props.get("title", "")
        doc_number = props.get("document_number", "")
        article_num = props.get("article_number", "")
        content = props.get("content", "")

        header = f"{doc_number} - Điều {article_num}"
        if title:
            header += f": {title}"
        lines.append(f"{header}\n{content}")

    return "\n\n".join(lines)


def build_prompt(question, context):
    return f"""Bạn là một trợ lý pháp lý chuyên nghiệp. Dựa vào các điều luật được cung cấp dưới đây, hãy trả lời câu hỏi của người dùng một cách chính xác và đầy đủ.

Nếu thông tin trong các điều luật không đủ để trả lời, hãy nói rõ là bạn không tìm thấy thông tin liên quan.

## Các điều luật liên quan:
{context}

## Câu hỏi của người dùng:
{question}

## Trả lời (bằng tiếng Việt, ngắn gọn, rõ ràng):"""

def send_request_to_groq(prompt):
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except groq.APIStatusError as e:
        print(f"Groq API Error: {e.status_code} - {e.message} - {e}")
        return f"❌ Lỗi từ phía Groq LLM: {e.status_code} - {e.message}"
    except Exception as e:
        print(f"Unexpected error when calling Groq API: {str(e)}")
        return f"❌ Đã xảy ra lỗi khi gọi Groq API: {str(e)}"

def chat_with_context(message, history, session_id):
    try:
        # 1. Gọi sang FastAPI lấy context
        payload = {
            "query": message,
            "top_k": 1,
            "alpha": 0.7,
            "session_id": session_id if isinstance(session_id, str) else ""
        }
        resp = requests.post(f"{FASTAPI_URL}/query_content", json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        print(result)
        
        context_text = format_context(result)
        user_prompt = build_prompt(message, context_text)
        print("User Prompt sent to Groq LLM:", user_prompt)  # Debug prompt trước khi gửi
        return send_request_to_groq(user_prompt)

    except groq.APIStatusError as e:
        # In ra terminal để bạn debug chính xác lỗi từ Groq
        print(f"Groq Error Detail: {e}")
        return f"❌ Lỗi từ phía Groq LLM: {e.status_code} - {e.message} - {e}"
    except requests.exceptions.ConnectionError:
        return "⚠️ Không thể kết nối đến FastAPI. Hãy đảm bảo service đang chạy."
    except Exception as e:
        return f"❌ Đã xảy ra lỗi hệ thống: {str(e)}"

# Thay vì dùng gr.ChatInterface ăn liền, ta bọc nó vào Blocks để quản lý State 
with gr.Blocks() as demo:
    # Khởi tạo một State ẩn để lưu trữ session_id, mặc định ban đầu là chuỗi rỗng ""
    session_state = gr.State(value="")
    
    gr.Markdown("# 🤖 Chatbot Pháp Luật")
    gr.Markdown("Hỏi đáp pháp luật Việt Nam - sử dụng RAG (Weaviate + Neo4j) + Groq LLM")
    
    # Khởi tạo ChatInterface bên trong Blocks
    chat_interface = gr.ChatInterface(
        fn=chat_with_context,
        additional_inputs=[session_state], # Đút State vào làm tham số thứ 3 của hàm xử lý
        examples=[
            ["Điều khiển xe máy sau khi uống rượu bia bị phạt gì?"],
            ["Tốc độ tối đa trên đường cao tốc là bao nhiêu?"],
            ["Điều kiện để được cấp giấy phép lái xe hạng B1?"],
        ],
    )

if __name__ == "__main__":
    # test 1 call to Groq LLM
    test_prompt = """ what is blackhole"""
    print('===============================================')
    response = send_request_to_groq(test_prompt)
    print(chat_with_context("Điều khiển xe máy sau khi uống rượu bia bị phạt gì?", [], "test-session-123"))
    # print("Groq LLM raw response:", response)
    # demo.launch(server_name="0.0.0.0", server_port=7860)