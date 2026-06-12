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
        content = props.get("content", "")
        lines.append(content)
    return "\n\n".join(lines)


def build_prompt(question, context, history=None):
    prompt = """Bạn là một trợ lý pháp lý chuyên nghiệp. Dựa vào các điều luật được cung cấp dưới đây, hãy trả lời câu hỏi của người dùng một cách chính xác và đầy đủ.

Nếu thông tin trong các điều luật không đủ để trả lời, hãy nói rõ là bạn không tìm thấy thông tin liên quan.

"""
    if history:
        lines = []
        for msg in history:
            role = "Người dùng" if msg["role"] == "user" else "Hệ thống"
            lines.append(f"{role}: {msg['content']}")
        prompt += "## Lịch sử hội thoại:\n" + "\n".join(lines) + "\n\n"

    prompt += f"""## Các điều luật liên quan:
{context}

## Câu hỏi của người dùng:
{question}

## Trả lời (bằng tiếng Việt, ngắn gọn, rõ ràng):"""
    return prompt


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
        err_body = e.body if hasattr(e, 'body') else str(e)
        print(f"Groq API Error: {e.status_code} - {err_body}")
        return f"Lỗi từ phía Groq LLM: {e.status_code} - {err_body}"
    except Exception as e:
        print(f"Unexpected error when calling Groq API: {str(e)}")
        return f"Đã xảy ra lỗi khi gọi Groq API: {str(e)}"


def respond(message, history, sessions, current_name):
    session = sessions.get(current_name, {"session_id": "", "history": []})
    session_id = session.get("session_id", "")

    try:
        payload = {
            "query": message,
            "top_k": 10,
            "alpha": 0.7,
            "session_id": session_id,
        }
        resp = requests.post(f"{FASTAPI_URL}/query_content", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        context_text = format_context(result)
        user_prompt = build_prompt(message, context_text, history)
        answer = send_request_to_groq(user_prompt)

        new_session_id = result.get("session_id", session_id)
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ]

        sessions[current_name] = {
            "session_id": new_session_id,
            "history": new_history,
        }
    except requests.exceptions.ConnectionError:
        answer = "Không thể kết nối đến FastAPI."
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ]
    except Exception as e:
        answer = f"Đã xảy ra lỗi: {str(e)}"
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ]

    return "", new_history, dict(sessions)


def new_session(sessions):
    name = f"Phiên {len(sessions) + 1}"
    sessions[name] = {"session_id": "", "history": []}
    return name, dict(sessions), [], gr.update(choices=list(sessions.keys()), value=name)


def switch_session(name, sessions):
    if name in sessions:
        session_data = sessions[name]
        history = session_data.get("history", [])
        if not history and session_data.get("session_id"):
            try:
                resp = requests.get(
                    f"{FASTAPI_URL}/session_history",
                    params={"session_id": session_data["session_id"]},
                    timeout=10,
                )
                if resp.ok:
                    api_history = resp.json().get("history", [])
                    if api_history:
                        history = [
                            {"role": m["role"], "content": m["content"]}
                            for m in api_history
                        ]
                        sessions[name]["history"] = list(history)
            except Exception:
                pass
    else:
        history = []
    return history, name


def delete_session(name, sessions):
    if name in sessions:
        del sessions[name]
    remaining = list(sessions.keys())
    if not remaining:
        name = "Phiên 1"
        sessions[name] = {"session_id": "", "history": []}
    else:
        name = remaining[0]
    return name, dict(sessions), sessions[name].get("history", []), gr.update(choices=list(sessions.keys()), value=name)


with gr.Blocks(title="Chatbot Pháp Luật", fill_height=True) as demo:
    default_name = "Phiên 1"
    sessions_state = gr.State(value={default_name: {"session_id": "", "history": []}})
    current_session = gr.State(value=default_name)

    gr.Markdown("# Chatbot Pháp Luật")
    gr.Markdown("Hỏi đáp pháp luật Việt Nam - RAG (Weaviate + Neo4j) + Groq LLM")

    with gr.Row():
        session_dropdown = gr.Dropdown(
            choices=[default_name],
            value=default_name,
            label="Chọn phiên",
            interactive=True,
            scale=3,
        )
        new_btn = gr.Button("+ Tạo phiên mới", scale=1, variant="primary")
        delete_btn = gr.Button("Xoá phiên", scale=1, variant="stop")

    chatbot = gr.Chatbot(
        label="Hội thoại",
        height=500,
    )

    msg = gr.Textbox(
        label="Nhập câu hỏi",
        placeholder="Ví dụ: Điều khiển xe máy sau khi uống rượu bia bị phạt gì?",
        submit_btn=True,
    )

    gr.Examples(
        examples=[
            ["Điều khiển xe máy sau khi uống rượu bia bị phạt gì?"],
            ["Tốc độ tối đa trên đường cao tốc là bao nhiêu?"],
            ["Điều kiện để được cấp giấy phép lái xe hạng B1?"],
        ],
        inputs=[msg],
    )

    msg.submit(
        fn=respond,
        inputs=[msg, chatbot, sessions_state, current_session],
        outputs=[msg, chatbot, sessions_state],
    )

    new_btn.click(
        fn=new_session,
        inputs=[sessions_state],
        outputs=[current_session, sessions_state, chatbot, session_dropdown],
    )

    delete_btn.click(
        fn=delete_session,
        inputs=[current_session, sessions_state],
        outputs=[current_session, sessions_state, chatbot, session_dropdown],
    )

    session_dropdown.change(
        fn=switch_session,
        inputs=[session_dropdown, sessions_state],
        outputs=[chatbot, current_session],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
