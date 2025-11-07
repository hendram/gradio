import gradio as gr
import requests
from datetime import datetime
import os
import re

# --- ADK Config ---
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

port = int(os.getenv("PORT", 80))

ADK_URL = os.getenv("ADK_URL")
APP_NAME = os.getenv("APP_NAME")
USER_ID = os.getenv("USER_ID")
SESSION_FILE = "/tmp/adk_session.txt"

conversation = []

# --- Session management ---
def load_session():
    try:
        with open(SESSION_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_session(session_id):
    with open(SESSION_FILE, "w") as f:
        f.write(session_id)

def get_or_create_session():
    session_id = load_session()
    
    if session_id:
        # Optional: test session validity
        try:
            resp = requests.post(f"{ADK_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions/{session_id}/ping")
            if resp.status_code == 200:
                return session_id
        except Exception:
            pass  # invalid session, will create new

    # Create new session
    resp = requests.post(f"{ADK_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions", json={})
    resp.raise_for_status()
    session_id = resp.json()["id"]  # <- the session ID is in 'id'
    save_session(session_id)
    return session_id

# --- Query ADK agent ---

def markdown_table_to_html(md_text: str) -> str:
    """
    Converts a Markdown table into an HTML table.
    """
    lines = md_text.strip().splitlines()
    if len(lines) < 2:
        return md_text  # Not a table
    
    # Check for table header separator line (---)
    if not re.match(r"^\s*\|?\s*[-:]+\s*(\|[-:]+\s*)+\|?\s*$", lines[1]):
        return md_text  # Not a table
    
    # Split lines into cells
    rows = [re.split(r"\s*\|\s*", line.strip("| ")) for line in lines]
    
    html = '<table border="1" style="border-collapse:collapse; width:100%;">\n'
    # Header
    html += "<tr>" + "".join(f"<th>{cell}</th>" for cell in rows[0]) + "</tr>\n"
    # Data rows
    for row in rows[2:]:  # skip separator line
        html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>\n"
    html += "</table>"
    return html


def query_agent(prompt: str):
    global conversation
    session_id = get_or_create_session()
    
    payload = {
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": session_id,
        "new_message": {"role": "user", "parts": [{"text": prompt}]}
    }
    
    try:
        resp = requests.post(f"{ADK_URL}/run", json=payload)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"<div style='color:red;'>Error: {e}</div>"

    # -------------------------
    # Extract RootAgent response
    # -------------------------
    root_responses_set = set()
    for item in data:
        if item.get("author") == "RootAgent":
            for part in item.get("content", {}).get("parts", []):
                if "text" in part and part.get("name") != "SemanticAgent":
                    root_responses_set.add(part["text"])

    final_responses = list(root_responses_set)
    final_text = "\n\n".join(final_responses) if final_responses else "<i>No response from RootAgent</i>"

    # -------------------------
    # Convert Markdown tables to HTML tables
    # -------------------------
    final_text = re.sub(
        r"(\|.+\|\n\|[-:| ]+\|(?:\n\|.*\|)+)", 
        lambda m: markdown_table_to_html(m.group(0)),
        final_text,
        flags=re.MULTILINE
    )

    # -------------------------
    # Append to conversation
    # -------------------------
    timestamp = datetime.now().strftime("%H:%M")
    conversation.append({"role": "user", "text": prompt, "time": timestamp})
    conversation.append({"role": "agent", "text": final_text, "time": timestamp})

    # -------------------------
    # Render chat bubbles
    # -------------------------
    chat_html = '<div style="display:flex; flex-direction:column;">'
    for msg in conversation:
        if msg["role"] == "user":
            chat_html += f"""
            <div style="align-self:flex-end; background:#DCF8C6; color:#000;
                        padding:8px 12px; border-radius:15px 15px 0 15px;
                        margin:4px 0; max-width:70%;">
                {msg['text']}<div style="font-size:10px; text-align:right;">{msg['time']}</div>
            </div>
            """
        else:
            chat_html += f"""
            <div style="align-self:flex-start; background:#FFFFFF; color:#000;
                        padding:8px 12px; border-radius:15px 15px 15px 0;
                        margin:4px 0; max-width:70%; border:1px solid #ccc;">
                {msg['text']}
                <div style="font-size:10px; text-align:right;">{msg['time']}</div>
            </div>
            """
    chat_html += "</div><script>var chat = document.getElementById('chatbox'); chat.scrollTop = chat.scrollHeight;</script>"
    return chat_html

# --- Gradio UI ---
with gr.Blocks() as demo:
    gr.HTML("""
    <style>
    body { font-family: Arial, sans-serif; background: #f0f2f5; }
    #chatbox { height: 400px; overflow-y:auto; padding:10px; border:1px solid #ccc; border-radius:8px; background:#e5ddd5; margin-bottom:10px; display:flex; flex-direction:column;}
    .my-btn button { background-color:#4CAF50; color:white; border-radius:12px; padding:10px 20px; border:none; font-size:16px; cursor:pointer; }
    .my-btn button:hover { background-color:#45a049; }
    #user_input textarea { font-size:16px; padding:8px; border-radius:8px; border:1px solid #ccc; width:100%; }
    .svelte-czcr5b { display: none }
   </style>
    """)

    gr.Markdown("## Mobile Ads Analytics Agent", elem_id="header")
    chatbox = gr.HTML("", elem_id="chatbox")
    user_input = gr.Textbox(
        placeholder="Type your message here...",
        lines=3,
        max_lines=10,
        elem_id="user_input"
    )
    submit = gr.Button("Send", elem_classes="my-btn")
    
    submit.click(query_agent, inputs=user_input, outputs=chatbox)
    user_input.submit(query_agent, inputs=user_input, outputs=chatbox)

demo.launch(server_name="0.0.0.0", server_port=port)
