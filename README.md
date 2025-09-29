# Dr. Cassandra — Your Single Plane for Diagnostic and Remediation of Livesite for  Apache Cassandra

**Faster incident resolution. Better customer experience. One-stop Cassandra diagnostics.**

## Problem Statement

**Apache Cassandra is a distributed NoSQL database that presents unique operational challenges:**

### Cassandra's Distributed Nature
- **Multi-Node Architecture**: Data distributed across multiple nodes in a cluster
- **Replication Strategy**: Data replicated across different data centers and racks
- **Consistency Levels**: Tunable consistency vs. availability trade-offs
- **Gossip Protocol**: Peer-to-peer communication for cluster membership and health
- **Anti-Entropy**: Background repair processes to maintain data consistency
- **Compaction**: Continuous background processes to optimize storage and performance

### Current Cassandra incident response is fragmented and inefficient:

### Diagnostic Challenges
- 🔍 **Scattered Tools**: Multiple monitoring tools, each with different interfaces and data formats
- ⏱️ **Manual Correlation**: Engineers spend hours manually connecting symptoms across metrics, logs, and topology
- 🔗 **Missing Context**: Critical relationships between symptoms and root causes are often overlooked
- 📊 **Data Silos**: Information exists in separate systems without unified correlation
- 🌐 **Distributed Complexity**: Issues can span multiple nodes, data centers, and replication factors
- ⚖️ **Consistency vs Availability**: Balancing CAP theorem trade-offs during incidents
- 🔄 **Gossip & Anti-Entropy**: Understanding cluster membership and repair status across nodes

### Remediation Challenges  
- 📋 **Disconnected Action Plans**: Remediation steps exist in separate runbooks, wikis, or tribal knowledge
- 🎯 **Generic Solutions**: One-size-fits-all approaches that don't account for specific cluster states
- ⚡ **Slow Response**: Time lost switching between diagnostic tools and hunting for relevant solutions
- 🚨 **High MTTR**: Mean Time To Resolution remains high due to fragmented workflows
- 🏗️ **Distributed Remediation**: Coordinating fixes across multiple nodes and data centers
- ⚙️ **Configuration Complexity**: Managing keyspace, table, and node-level settings during incidents
- 🔧 **Safe Operations**: Ensuring repairs, compactions, and node operations don't cause cascading failures

### Business Impact
- **Customer Experience**: Extended downtime affects user satisfaction
- **Engineering Productivity**: Teams spend more time on incident response than feature development
- **Operational Costs**: Manual processes are expensive and error-prone

## Solution Statement

**Dr. Cassandra provides an integrated diagnostic and remediation platform that unifies the entire incident response workflow:**

### Unified Diagnostic Engine
- **Single Interface**: One platform orchestrating all diagnostic tools and data sources
- **Intelligent Correlation**: AI automatically identifies relationships between symptoms, metrics, logs, and topology
- **Contextual Analysis**: Real-time correlation across multiple data dimensions
- **Automated Discovery**: Dynamic tool discovery and integration via MCP protocol
- **Distributed Awareness**: Understanding cluster topology, replication factors, and data center distribution
- **Gossip & Membership**: Real-time cluster health and node status monitoring
- **Consistency Analysis**: Evaluating CAP theorem implications for specific operations

### Integrated Remediation System
- **Context-Aware Action Plans**: Remediation steps generated directly from diagnostic findings
- **Tailored Guidance**: Step-by-step instructions specific to your cluster's current state
- **Multi-Tool Orchestration**: Seamless execution across diagnostic and control tools
- **Progressive Enhancement**: Plans that adapt as new diagnostic information becomes available
- **Distributed Coordination**: Safe execution of repairs, compactions, and node operations across the cluster
- **Configuration Management**: Intelligent keyspace and table-level setting adjustments
- **Risk Assessment**: Evaluating impact of operations before execution to prevent cascading failures

### Business Benefits
- **Faster MTTR**: Reduce incident resolution time from hours to minutes
- **Improved Reliability**: Proactive issue detection and automated remediation
- **Enhanced Productivity**: Engineers focus on strategic work, not manual correlation
- **Better Customer Experience**: Reduced downtime and faster issue resolution

The system pairs a FastAPI web interface with an MCP server that exposes Cassandra inventory, metrics, logs, and control tools. The AI agent discovers capabilities dynamically and orchestrates multiple diagnostic tools in sequence to provide comprehensive incident analysis and remediation guidance.

## Demo Video

> **🎬 Click to watch the full demo video**

[![Dr. Cassandra Demo](https://img.shields.io/badge/▶️-Watch%20Demo%20Video-red?style=for-the-badge&logo=youtube)](./assets/cassandra_doctor_demo.mov)

**Direct link:** [cassandra_doctor_demo.mov](./assets/cassandra_doctor_demo.mov)

*Watch Dr. Cassandra in action - setting up the MCP server, asking cluster health questions, and demonstrating the multi-tool investigation workflow.*

**Note:** The video will open in a new tab/window when clicked. For the best viewing experience, download the video file to your device.

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


