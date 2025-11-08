import os
import re
import json
import uuid
import base64
import requests
import plotly.express as px
import plotly.graph_objects as go
import gradio as gr
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

# ==================================================
# --- ADK Configuration ---
# ==================================================
load_dotenv()
port = int(os.getenv("PORT", 80))
ADK_URL = os.getenv("ADK_URL")
APP_NAME = os.getenv("APP_NAME")
USER_ID = os.getenv("USER_ID")
SESSION_FILE = "/tmp/adk_session.txt"

conversation = []

# ==================================================
# --- Session Management ---
# ==================================================
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
            pass  # invalid session, create new

    # Create new session
    resp = requests.post(f"{ADK_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions", json={})
    resp.raise_for_status()
    session_id = resp.json()["id"]
    save_session(session_id)
    return session_id


# ==================================================
# --- Markdown Table to HTML ---
# ==================================================
def markdown_table_to_html(md_text: str) -> str:
    """Convert Markdown table into an HTML table."""
    lines = md_text.strip().splitlines()
    if len(lines) < 2:
        return md_text  # Not a table

    # Check for table header separator line (---)
    if not re.match(r"^\s*\|?\s*[-:]+\s*(\|[-:]+\s*)+\|?\s*$", lines[1]):
        return md_text  # Not a table

    # Split lines into cells
    rows = [re.split(r"\s*\|\s*", line.strip("| ")) for line in lines]

    html = '<table border="1" style="border-collapse:collapse; width:100%;">\n'
    html += "<tr>" + "".join(f"<th>{cell}</th>" for cell in rows[0]) + "</tr>\n"

    for row in rows[2:]:  # skip separator line
        html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>\n"

    html += "</table>"
    return html


# ==================================================
# --- Plotly Graph ---
# ==================================================
def plot_graph_from_json(graph_data):
    try:
        points = graph_data.get("points", [])
        if not points:
            fig = go.Figure()
            fig.add_annotation(
                text="No points data to plot",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(color="red", size=16)
            )
            return fig

        x = [p['x'] for p in points]
        y = [p['y'] for p in points]

        fig = px.scatter(
            x=x, y=y,
            labels={
                'x': graph_data.get("xAxis", "X"),
                'y': graph_data.get("yAxis", "Y")
            },
            title="🚗 Vehicle Distance vs Cost",
            color=y,
            color_continuous_scale="Turbo"
        )

        fig.update_traces(
            marker=dict(size=14, opacity=0.8, line=dict(width=2, color='DarkSlateGrey'))
        )

        fig.update_layout(
            template="plotly_white",
            height=600,
            width=900,
            margin=dict(l=60, r=40, t=80, b=60),
            title_font=dict(size=20, color="#1E90FF"),
            plot_bgcolor="rgba(250,250,255,1)",
            paper_bgcolor="rgba(255,255,255,1)"
        )
        return fig

    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error rendering graph: {e}",
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(color="red", size=16)
        )
        return fig


# ==================================================
# --- Query ADK Agent ---
# ==================================================
def query_agent(prompt: str):
    global conversation

    # --- Reset graph visibility on each new send ---
    graph_visibility = gr.update(visible=False)

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
        return f"<div style='color:red;'>Error: {e}</div>", graph_visibility

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
    # Detect if graph JSON exists
    # -------------------------
    fig = None
    try:
        points_list = None
        code_block_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", final_text, re.DOTALL)
        if code_block_match:
            try:
                points_list = json.loads(code_block_match.group(1))
            except Exception:
                pass
        if not points_list:
            matches = re.findall(r'\{\s*"x"\s*:\s*([\d.]+)\s*,\s*"y"\s*:\s*([\d.]+)\s*\}', final_text)
            if matches:
                points_list = [{"x": float(x), "y": float(y)} for x, y in matches]

        if points_list:
            fig = plot_graph_from_json({
                "xAxis": "Cost (USD)",
                "yAxis": "Distance (m)",
                "points": points_list
            })
    except Exception:
        fig = None

    # -------------------------
    # Convert Markdown tables
    # -------------------------
    if final_text:
        final_text = re.sub(
            r"(\|.+\|\n\|[-:| ]+\|(?:\n\|.*\|)+)",
            lambda m: markdown_table_to_html(m.group(0)),
            final_text,
            flags=re.MULTILINE,
        )

    # -------------------------
    # Append to chat
    # -------------------------
    timestamp = datetime.now().strftime("%H:%M")
    conversation.append({"role": "user", "text": prompt, "time": timestamp})
    conversation.append({"role": "agent", "text": final_text, "time": timestamp})

    # -------------------------
    # Render chat bubbles
    # -------------------------
    chat_html = '<div style="display:flex; flex-direction:column;">'
    for msg in conversation:
        content = msg["text"]
        if msg["role"] == "user":
            chat_html += f"""
                <div style="align-self:flex-end; background:#DCF8C6; color:#000;
                padding:8px 12px; border-radius:15px 15px 0 15px; margin:4px 0;
                max-width:70%;">
                {content}
                <div style="font-size:10px; text-align:right;">{msg['time']}</div>
                </div>
            """
        else:
            chat_html += f"""
                <div style="align-self:flex-start; background:#FFFFFF; color:#000;
                padding:8px 12px; border-radius:15px 15px 15px 0; margin:4px 0;
                max-width:70%; border:1px solid #ccc;">
                {content}
                <div style="font-size:10px; text-align:right;">{msg['time']}</div>
                </div>
            """
    chat_html += "</div>"
    chat_html += "<script>var chat=document.getElementById('chatbox');if(chat)chat.scrollTop=chat.scrollHeight;</script>"

    # -------------------------
    # Show or hide graph
    # -------------------------
    if fig is None:
        return chat_html, gr.update(visible=False)
    else:
        return chat_html, gr.update(value=fig, visible=True)

# ==================================================
# --- Gradio UI ---
# ==================================================
with gr.Blocks(css="#graph-box { width:100% !important; min-height:600px !important; }") as demo:
    gr.HTML("""
    <script src="https://cdn.plot.ly/plotly-3.1.0.min.js"></script>
    <style>
    body { font-family: Arial, sans-serif; background: #f0f2f5; }
    #chatbox { height: 400px; overflow-y:auto; padding:10px; border:1px solid #ccc;
        border-radius:8px; background:#e5ddd5; margin-bottom:10px;
        display:flex; flex-direction:column; }
    footer { display:none !important; }
    </style>
    """)

    gr.Markdown("""
    <h2 style="text-align:center; color:#003366; font-family:'Segoe UI', sans-serif;
    font-size:2vw; background:linear-gradient(to right,#E0F7FA,#E3F2FD);
    padding:12px; border-radius:0.5vw; box-shadow:0 2px 6px rgba(0,0,0,0.15);">
    🚗 Mobile Ads Car Analytics Agent
    </h2>
    """)

    chatbox = gr.HTML("", elem_id="chatbox")
    graph_output = gr.Plot(label="Graph Output", elem_id="graph-box", visible=False)
    user_input = gr.Textbox(
        label="User Query:",
        placeholder="Type your message here...",
        lines=3,
        max_lines=10,
        elem_id="user_input"
    )

    submit = gr.Button("Send")

    # 🔹 Step 1: Immediately hide graph when Send pressed (before query_agent runs)
    submit.click(lambda: gr.update(visible=False), None, graph_output)

    # 🔹 Step 2: Run query_agent and update graph visibility depending on result
    submit.click(query_agent, inputs=user_input, outputs=[chatbox, graph_output])
    user_input.submit(query_agent, inputs=user_input, outputs=[chatbox, graph_output])

demo.launch(server_name="0.0.0.0", server_port=port)
