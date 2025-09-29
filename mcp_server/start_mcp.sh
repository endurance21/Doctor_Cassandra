python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORT=8001
fastmcp run mcp_server.py --transport sse --host 127.0.0.1 --port $PORT