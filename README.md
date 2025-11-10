# 🚗 Mobile Ads Car Analytics Agent

This project provides a web-based analytics agent for monitoring and analyzing mobile car trips and ad campaigns. It leverages **Google ADK agents**, **Firestore**, and **Plotly** to fetch, process, and visualize car trip data in real-time.

---

## Features

- Persistent session management with ADK backend.
- Query and fetch data from ADK RootAgent and Semantic Agents.
- Convert Markdown tables from agent responses into HTML for readable chat.
- Render Plotly graphs for trip analytics such as distance vs cost.
- Chat-style interface with user messages and agent responses.
- Supports queries related to fuel cost, driver cost, trip count, elapsed time, and graph plotting.

---

## Usage
Open the app in a browser.

Type a query in the User Query box.

Submit your query; the agent responds in the chat box.

If the response contains graph data, a Plotly graph is rendered below the chat.

Tables in Markdown format are automatically converted to HTML tables for readability.

## Code Overview

### Session Management

Session persistence: SESSION_FILE stores the current ADK session.

get_or_create_session(): Ensures a valid session exists; creates a new session if none exists or the old one is invalid.

## Query Processing

query_agent(prompt: str):

Sends user input to the ADK backend.

Fetches RootAgent responses.

Extracts and renders Markdown tables as HTML.

Detects JSON-formatted graph points and renders them using Plotly.

Appends user and agent messages to the chat history.

## Graph Rendering

plot_graph_from_json(graph_data):

Accepts JSON input in the format {"xAxis": ..., "yAxis": ..., "points": [{"x": ..., "y": ...}, ...]}.

Uses Plotly Express to create scatter plots.

Styles graph with customized markers, color scale, and background.

## Markdown Table Conversion

markdown_table_to_html(md_text):

Detects Markdown tables in agent responses.

Converts them to HTML <table> elements for rich chat rendering.

## Gradio Interface

Chatbox: Displays conversation history.

User Input: Multi-line textbox for queries.

Graph Output: Conditional Plotly graph rendered if the agent response contains graph data.

Send Button: Submits query to agent and updates chat + graph.

## Example Chat Flow
User: "Calculate total fuel cost for car1 latest trip with x/y points per leg."

Agent: Responds with HTML tables and optionally a graph visualization.

## Technologies Used

Python 3.10+

Gradio – Web interface for chat and graph.

Plotly – Graph rendering for analytics.

Requests – API communication with ADK backend.

dotenv – Environment variable management.

ADK Agents – RootAgent and Semantic Agents handle analytic queries.

