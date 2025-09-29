# Dr. Cassandra — Agentic Web (MCP Chat + Server)

Dr. Cassandra is a live site manager for Apache Cassandra built on the Model Context Protocol (MCP). It pairs:

- A FastAPI web chat client that connects to an MCP server
- An MCP server exposing Cassandra-like inventory, metrics, logs, and control tools (mocked for demo)

The agent discovers tools/resources dynamically via MCP and can call multiple tools in sequence to investigate issues and produce actionable guidance.

## Tech Stack

- FastAPI (Python) — web server for chat UI and API
- Vanilla HTML/CSS/JS — chat front-end with hover notifications and keyboard UX
- OpenAI API — model for planning/tool-use and answers
- MCP (Python SDK) — client and server communication
- FastMCP — rapid MCP server scaffolding and ergonomics

## Repository Layout

- `chat_agent/`
  - `chat_agent.py` — FastAPI app and MCP client (SSE or STDIO)
  - `index.html` — modern chat UI with notifications and Enter-to-send
  - `requirements.txt` — web app dependencies
  - `start_chat_agent.sh` — convenience runner for the chat app
- `mcp_server/`
  - `mcp_server.py` — MCP server exposing Cassandra tools/resources
  - `providers/` — mock providers for inventory, metrics, logs, node control
  - `start_mcp.sh` — convenience runner for the server
  - `requirements.txt` — server dependencies
- `start_chat_agent.sh` / `start_mcp_server.sh` / `start.sh` — root helpers

## Features

- Dynamic MCP discovery (no hardcoded tool schemas)
- Multi-round tool calling loop (the model may call several tools before answering)
- SSE transport (connect to an already running server) or STDIO (spawn server)
- Modern UI: gradient theme, bubble chat, keyboard shortcuts, dismissible hover notifications

## Quick Start

Prereqs: Python 3.10+ and an OpenAI API key.

1) Set environment

```bash
export OPENAI_API_KEY=sk-...        # required
# Optional: choose model
export OPENAI_MODEL=gpt-4o-mini
```

2) Install chat app deps (virtualenv recommended)

```bash
cd chat_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install mcp               # MCP Python SDK (client)
```

3) Install MCP server deps

```bash
cd ../mcp_server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt || true
pip install fastmcp            # server helper
```

4) Run server and chat app (two shells)

Shell A (MCP server):

```bash
cd mcp_server
./start_mcp.sh
# or: python3 mcp_server.py
```

Shell B (Chat app):

```bash
cd chat_agent
./start_chat_agent.sh
# or: uvicorn chat_agent:app --reload --port 8000
```

Open the UI at http://127.0.0.1:8000/

## Connection Modes (MCP)

The chat client can connect to the MCP server via:

- SSE (HTTP) — point to an already running MCP server
  - Set `MCP_URL=http://127.0.0.1:8001` (or your server URL)
  - Requires `pip install "mcp>=1.9"`

- STDIO (local spawn) — start server as a subprocess
  - Defaults if `MCP_URL` is unset
  - Config via:
    - `PYTHON_BIN` (default: `python`)
    - `MCP_ENTRY` (default: `server.py`, adjust to your entry file)

## API Endpoints

- `GET /` — Serves the chat UI (`index.html`)
- `POST /chat` — Accepts `{ message, session_id }`, orchestrates MCP discovery and multi-round tool calls, returns `{ reply, tools }`

## MCP Server (Dr. Cassandra)

The server provides Cassandra-oriented tools/resources (mocked):

- Resources
  - `cassandra://inventory/customers`
  - `cassandra://inventory/{customer}/clusters`
  - `cassandra://cluster/{customer}/{cluster}/topology`
- Tools (examples)
  - `list_clusters(customer=None)` — list clusters globally or for a customer
  - `cluster_overview(customer, cluster)` — topology summary and KPIs
  - `node_health(customer, cluster, node)` — status/load/latency/timeouts/disk%
  - `query_metrics(customer, cluster, metric, window="15m")` — mocked time series
  - `fetch_logs(customer, cluster, node=None, pattern=None, since="15m", limit=200)`
  - `restart_node(customer, cluster, node)` — mocked control action
  - `advise_capacity(customer, cluster)` — mocked scaling suggestion

These are discovered dynamically by the client; no schema is hardcoded in prompts.

## Using the Chat UI

- Type a question; press Enter to send (Shift+Enter for new line)
- Notifications appear as hover toasts; click to dismiss
- When the MCP server exposes tools, the UI shows an indicator

Example prompts:

- "List all clusters"
- "Give me an overview of cluster nova-prod for Contoso"
- "What is the health of node 10.0.1.11 in nova-prod?"
- "Why is p99 read latency high on nova-prod?" (the agent may call multiple tools)

## Environment Variables

- `OPENAI_API_KEY` — required
- `OPENAI_MODEL` — default `gpt-4o-mini`
- `MCP_URL` — if set, client uses SSE transport to connect to an existing server
- `PYTHON_BIN` — when spawning server via STDIO
- `MCP_ENTRY` — entry script for spawned server (default `server.py`)

## Development

- The chat agent logs MCP discovery, tool calls, and model responses to the console
- The client implements a multi-round loop: after each tool call, it re-asks the model until a final answer (or round cap) is reached
- The server providers in `mcp_server/providers/` are mock implementations; swap with real ones when ready

## Extending to a Generic Live Site Manager

This pattern is generic. To manage other systems:

1. Implement a new MCP server with tools/resources for the target domain
2. Keep the chat agent unchanged — it discovers tools dynamically
3. Encourage multi-step diagnostics (overview → metrics → logs → control)

Rename the persona as needed (e.g., "Dr. Postgres", "Dr. Kafka"). Here, it’s configured as "Dr. Cassandra".

## Troubleshooting

- "Cannot import MCP" — ensure the chat venv has `mcp` installed
- "No module fastmcp" — install `fastmcp` in the server environment
- Empty answers after tool calls — check console logs; the loop continues until the model emits content without new tool calls
- SSE connection errors — verify `MCP_URL` is reachable and server is running

## License

MIT (unless otherwise noted).


