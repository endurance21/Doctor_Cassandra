import os
import json
import contextlib
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse

load_dotenv()

# --- OpenAI (new SDK preferred; fallback to legacy) ---
USE_NEW_OPENAI = False
try:
    from openai import OpenAI
    oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    USE_NEW_OPENAI = True
except Exception:
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")

# --- MCP client(s) ---
# pip install "mcp>=1.9"
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# SSE client (connects to server already running over HTTP/SSE)
try:
    from mcp.client.sse import sse_client
    HAS_SSE = True
except Exception:
    HAS_SSE = False

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# If MCP_URL is set, we use SSE (network). Otherwise we fall back to STDIO (spawn).
MCP_URL = os.getenv("MCP_URL", "").strip()
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")
MCP_ENTRY  = os.getenv("MCP_ENTRY", "server.py")
MCP_COMMAND = [PYTHON_BIN, MCP_ENTRY]

BASE_SYSTEM_PROMPT = """You are Cassandra Doctor — an expert SRE/DBA assistant for Apache Cassandra clusters.

IMPORTANT: Always use the available MCP tools to answer questions. The tools and their schemas are provided to you dynamically.

ALWAYS call the appropriate tool(s) first before providing an answer. If you don't have the data, use the tools to get it.

Be concise and specific. Warn before any disruptive actions. Return clear steps and brief rationale.
"""

app = FastAPI()
SESSIONS: Dict[str, List[Dict[str, Any]]] = {}

def build_dynamic_system_prompt(mcp_tools: List[Any], mcp_resources: List[Any]) -> str:
    """Build a dynamic system prompt that includes discovered tools and resources."""
    prompt = BASE_SYSTEM_PROMPT + "\n\n"
    
    if mcp_tools:
        prompt += "AVAILABLE TOOLS:\n"
        for tool in mcp_tools:
            prompt += f"- {tool.name}: {tool.description or 'No description'}\n"
            
            # Check for different possible schema attributes
            schema = None
            if hasattr(tool, 'input_schema') and tool.input_schema:
                schema = tool.input_schema
            elif hasattr(tool, 'inputSchema') and tool.inputSchema:
                schema = tool.inputSchema
            elif hasattr(tool, 'parameters') and tool.parameters:
                schema = tool.parameters
            elif hasattr(tool, 'args') and tool.args:
                schema = tool.args
            
            if schema:
                prompt += f"  Parameters: {json.dumps(schema, indent=2)}\n"
            else:
                # Debug: show what attributes the tool actually has
                prompt += f"  Available attributes: {[attr for attr in dir(tool) if not attr.startswith('_')]}\n"
        prompt += "\n"
    
    if mcp_resources:
        prompt += "AVAILABLE RESOURCES:\n"
        for resource in mcp_resources:
            prompt += f"- {resource.uri}: {resource.description or 'No description'}\n"
        prompt += "\n"
    
    prompt += "Use the tools and resources above to answer questions. Always call the appropriate tool first to get data before responding."
    
    return prompt

def build_messages(session_id: str, mcp_tools: List[Any] = None, mcp_resources: List[Any] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
    msgs = SESSIONS.setdefault(session_id, [])
    
    # Build dynamic system prompt if tools/resources are provided
    if mcp_tools is not None or mcp_resources is not None:
        system_prompt = build_dynamic_system_prompt(mcp_tools or [], mcp_resources or [])
        
        # Check if we need to update the system prompt
        current_system = msgs[0] if msgs and msgs[0].get("role") == "system" else None
        should_update = force_refresh or not current_system or current_system["content"] != system_prompt
        
        if should_update:
            if current_system:
                # Update existing system message
                msgs[0]["content"] = system_prompt
                print(f"Updated system prompt for session {session_id}")
            else:
                # Insert new system message
                msgs.insert(0, {"role": "system", "content": system_prompt})
                print(f"Created new system prompt for session {session_id}")
    elif not msgs or msgs[0].get("role") != "system":
        # Fallback to base prompt if no tools/resources provided
        msgs.insert(0, {"role": "system", "content": BASE_SYSTEM_PROMPT})
    
    return msgs

def to_openai_tool(mcp_tool: Any) -> Dict[str, Any]:
    # Check for different possible schema attributes
    schema = None
    if hasattr(mcp_tool, 'input_schema') and mcp_tool.input_schema:
        schema = mcp_tool.input_schema
    elif hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
        schema = mcp_tool.inputSchema
    elif hasattr(mcp_tool, 'parameters') and mcp_tool.parameters:
        schema = mcp_tool.parameters
    elif hasattr(mcp_tool, 'args') and mcp_tool.args:
        schema = mcp_tool.args
    else:
        schema = {"type": "object", "properties": {}}
    
    return {"type": "function", "function": {"name": mcp_tool.name, "description": mcp_tool.description or "", "parameters": schema}}

def clean_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure all messages have valid content fields for OpenAI API."""
    cleaned = []
    for msg in messages:
        cleaned_msg = msg.copy()
        # Ensure content is always a string, never None
        if "content" in cleaned_msg and cleaned_msg["content"] is None:
            cleaned_msg["content"] = ""
        elif "content" not in cleaned_msg:
            cleaned_msg["content"] = ""
        cleaned.append(cleaned_msg)
    return cleaned

async def call_openai(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Clean messages to ensure no null content values
    cleaned_messages = clean_messages(messages)
    
    if USE_NEW_OPENAI:
        return oai_client.chat.completions.create(
            model=OPENAI_MODEL, messages=cleaned_messages, tools=tools, tool_choice="auto", temperature=0.2
        ).model_dump()
    else:
        return openai.ChatCompletion.create(
            model=OPENAI_MODEL, messages=cleaned_messages, tools=tools, tool_choice="auto", temperature=0.2
        )

async def mcp_connect_network():
    """Connect to an already-running MCP server over SSE."""
    if not HAS_SSE:
        print("mcp.client.sse is unavailable; upgrade mcp package (pip install 'mcp>=1.9').")
        raise RuntimeError("mcp.client.sse is unavailable; upgrade mcp package (pip install 'mcp>=1.9').")
    if not MCP_URL:
        print("MCP_URL not set. Example: MCP_URL=http://127.0.0.1:8001")
        raise RuntimeError("MCP_URL not set. Example: MCP_URL=http://127.0.0.1:8001")
    print(f"reached here....")
    stack = AsyncExitStack()
    print(f"stack: {stack}")
    await stack.__aenter__()
    print(f"stack entered 2")
    print(f"stack entered")
    reader, writer = await stack.enter_async_context(sse_client(MCP_URL))
    print(f"reader, writer: {reader, writer}")
    print(f"reader: {reader}")
    print(f"writer: {writer}")
    session = await stack.enter_async_context(ClientSession(reader, writer))
    print(f"session: {session}")
    await session.initialize()  
    print(f"session initialized")
    return session, stack

async def mcp_connect_stdio():
    """Spawn the MCP server over STDIO (fallback)."""
    params = StdioServerParameters(command=MCP_COMMAND[0], args=MCP_COMMAND[1:])
    stack = AsyncExitStack()
    await stack.__aenter__()
    reader, writer = await stack.enter_async_context(stdio_client(params))
    session = await stack.enter_async_context(ClientSession(reader, writer))
    await session.initialize()
    return session, stack

async def mcp_discover(session: ClientSession) -> Dict[str, Any]:
    tools_resp = await session.list_tools()
    res_resp = await session.list_resources()
    print(f"mcp_discover tools: {tools_resp.tools}")
    print(f"mcp_discover resources: {res_resp.resources}")
    return {"tools": tools_resp.tools or [], "resources": res_resp.resources or []}

async def mcp_call_tool(session: ClientSession, name: str, args: Dict[str, Any]) -> str:
    print(f"mcp_call_tool: {name}, {args}")
    result = await session.call_tool(name=name, arguments=args or {})
    print(f"mcp_call_tool result: {result}")
    print(f"mcp_call_tool result type: {type(result)}")
    print(f"mcp_call_tool result attributes: {dir(result)}")
    
    parts: List[str] = []
    
    # Handle different result formats
    if hasattr(result, 'content') and result.content:
        # Standard MCP format with content
        for item in result.content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(text)
            else:
                with contextlib.suppress(Exception):
                    parts.append(json.dumps(item.model_dump(), ensure_ascii=False))
    elif hasattr(result, 'text') and result.text:
        # Direct text result
        parts.append(result.text)
    else:
        # Try to serialize the entire result object
        try:
            if hasattr(result, 'model_dump'):
                parts.append(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
            else:
                parts.append(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            parts.append(f"Error serializing result: {e}")
            parts.append(str(result))
    
    result_text = "\n".join(parts) if parts else "(no result)"
    print(f"mcp_call_tool final result: {result_text}")
    return result_text

async def execute_tool_calls(session: ClientSession, tool_calls: List[Dict[str, Any]]) -> None:
    """Execute a list of tool calls and add results to messages."""
    for tc in tool_calls:
        name = tc["function"]["name"]
        args_json = tc["function"].get("arguments") or "{}"
        print(f"Executing tool: {name} with args: {args_json}")
        try:
            args = json.loads(args_json) if isinstance(args_json, str) else args_json
        except Exception:
            args = {}

        if name == "mcp_read_resource":
            result_text = await mcp_read_resource(session, args.get("uri", ""))
        else:
            result_text = await mcp_call_tool(session, name, args)

        print(f"Tool result for {name}: '{result_text}'")
        return result_text  # Return the last result for simplicity

async def mcp_read_resource(session: ClientSession, uri: str) -> str:
    print(f"mcp_read_resource: {uri}")
    res = await session.read_resource(uri)
    print(f"mcp_read_resource result: {res}")
    print(f"mcp_read_resource result type: {type(res)}")
    
    parts: List[str] = []
    
    # Handle different result formats
    if hasattr(res, 'content') and res.content:
        for item in res.content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(text)
            else:
                with contextlib.suppress(Exception):
                    parts.append(json.dumps(item.model_dump(), ensure_ascii=False))
    elif hasattr(res, 'text') and res.text:
        parts.append(res.text)
    else:
        try:
            if hasattr(res, 'model_dump'):
                parts.append(json.dumps(res.model_dump(), ensure_ascii=False, indent=2))
            else:
                parts.append(json.dumps(res, ensure_ascii=False, indent=2))
        except Exception as e:
            parts.append(f"Error serializing resource: {e}")
            parts.append(str(res))
    
    result_text = "\n".join(parts) if parts else "(no content)"
    print(f"mcp_read_resource final result: {result_text}")
    return result_text

RESOURCE_READER = {
    "type": "function",
    "function": {
        "name": "mcp_read_resource",
        "description": "Read a resource by URI exposed by the MCP server.",
        "parameters": {"type": "object", "properties": {"uri": {"type": "string"}}, "required": ["uri"], "additionalProperties": False},
    },
}

@app.get("/")
async def index():
    return FileResponse(Path(__file__).with_name("index.html"))

@app.post("/chat")
async def chat(req: Request):
    data = await req.json()
    user_text: str = (data.get("message") or "").strip()
    session_id: str = (data.get("session_id") or "default").strip()

    if not user_text:
        return JSONResponse({"error": "Empty message"}, status_code=400)
    if not os.getenv("OPENAI_API_KEY"):
        return JSONResponse({"error": "OPENAI_API_KEY not set"}, status_code=500)
    session = None
    stack = None
    try:
        # Prefer network if MCP_URL is set; else fallback to stdio spawn
        if MCP_URL:
            session, stack = await mcp_connect_network()
            print("mcp server connected over network")
        else:
            # Optional: guard against missing entry file when falling back
            if not Path(MCP_ENTRY).exists():
                return JSONResponse({"error": f"MCP_ENTRY not found: {MCP_ENTRY}"}, status_code=500)
            session, stack = await mcp_connect_stdio()

        discovered = await mcp_discover(session)
        mcp_tools = discovered["tools"]
        mcp_resources = discovered["resources"]
        
        print(f"Available MCP tools: {[t.name for t in mcp_tools]}")
        print(f"Available MCP resources: {[r.uri for r in mcp_resources]}")
        
        for tool in mcp_tools:
            print(f"Tool: {tool.name}")
            print(f"  Description: {tool.description}")
            print(f"  Tool type: {type(tool)}")
            print(f"  Tool attributes: {[attr for attr in dir(tool) if not attr.startswith('_')]}")
            
            # Try to find the schema attribute
            schema_attr = None
            for attr in ['input_schema', 'inputSchema', 'parameters', 'args']:
                if hasattr(tool, attr):
                    schema_attr = attr
                    break
            
            if schema_attr:
                print(f"  Schema attribute: {schema_attr} = {getattr(tool, schema_attr)}")
            else:
                print(f"  No schema attribute found")
        
        oai_tools = [to_openai_tool(t) for t in mcp_tools]
        oai_tools.append(RESOURCE_READER)
        print(f"OpenAI tools being sent: {[t['function']['name'] for t in oai_tools]}")

        # Build messages with dynamic system prompt that includes discovered tools/resources
        messages = build_messages(session_id, mcp_tools, mcp_resources)
        messages.append({"role": "user", "content": user_text})
        
        # Show the dynamic system prompt
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        if system_msg:
            print(f"Dynamic system prompt: {system_msg['content'][:300]}...")

        # Round 1 (let model decide to call tools)
        print(f"Sending to OpenAI - messages: {len(messages)}, tools: {len(oai_tools)}")
        print(f"Messages: {[{'role': m['role'], 'content': m['content'][:100] + '...' if len(m.get('content', '')) > 100 else m.get('content', '')} for m in messages]}")
        
        resp = await call_openai(messages, oai_tools)
        print(f"OpenAI response: {resp}")
        choice = (resp["choices"][0] if USE_NEW_OPENAI else resp.choices[0])
        msg = choice["message"] if USE_NEW_OPENAI else choice.message
        tool_calls = msg.get("tool_calls") if USE_NEW_OPENAI else getattr(msg, "tool_calls", None)
        print(f"Message content: {msg.get('content')}")
        print(f"Tool calls: {tool_calls}")
        print(f"Tool calls length: {len(tool_calls) if tool_calls else 0}")
        
        if tool_calls:
            print(f"AI decided to call {len(tool_calls)} tool(s)")
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
            for tc in tool_calls:
                name = tc["function"]["name"]
                args_json = tc["function"].get("arguments") or "{}"
                print(f"Calling tool: {name} with args: {args_json}")
                try:
                    args = json.loads(args_json) if isinstance(args_json, str) else args_json
                except Exception:
                    args = {}

                if name == "mcp_read_resource":
                    result_text = await mcp_read_resource(session, args.get("uri", ""))
                else:
                    result_text = await mcp_call_tool(session, name, args)

                print(f"Tool result for {name}: '{result_text}'")
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})

            # Keep calling OpenAI until we get a final response (no more tool calls)
            max_rounds = 5  # Prevent infinite loops
            for round_num in range(2, max_rounds + 1):
                print(f"Round {round_num} - calling OpenAI with {len(messages)} messages")
                resp = await call_openai(messages, oai_tools)
                print(f"Round {round_num} OpenAI response: {resp}")
                choice = (resp["choices"][0] if USE_NEW_OPENAI else resp.choices[0])
                msg = choice["message"] if USE_NEW_OPENAI else choice.message
                content = msg.get("content") or ""
                tool_calls = msg.get("tool_calls") if USE_NEW_OPENAI else getattr(msg, "tool_calls", None)
                
                print(f"Round {round_num} - Content: '{content}'")
                print(f"Round {round_num} - Tool calls: {len(tool_calls) if tool_calls else 0}")
                
                if tool_calls:
                    print(f"Round {round_num} - AI wants to make {len(tool_calls)} more tool calls")
                    messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                    
                    # Execute the tool calls
                    for tc in tool_calls:
                        name = tc["function"]["name"]
                        args_json = tc["function"].get("arguments") or "{}"
                        print(f"Round {round_num} - Calling tool: {name} with args: {args_json}")
                        try:
                            args = json.loads(args_json) if isinstance(args_json, str) else args_json
                        except Exception:
                            args = {}

                        if name == "mcp_read_resource":
                            result_text = await mcp_read_resource(session, args.get("uri", ""))
                        else:
                            result_text = await mcp_call_tool(session, name, args)

                        print(f"Round {round_num} - Tool result for {name}: '{result_text}'")
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})
                else:
                    # No more tool calls, we have our final answer
                    print(f"Round {round_num} - Final answer: '{content}'")
                    messages.append({"role": "assistant", "content": content})
                    SESSIONS[session_id] = messages
                    return JSONResponse({"reply": content, "tools": [t.name for t in mcp_tools]})
            
            # If we hit max rounds, return the last content
            print(f"Hit max rounds ({max_rounds}), returning last response")
            messages.append({"role": "assistant", "content": content})
            SESSIONS[session_id] = messages
            return JSONResponse({"reply": content, "tools": [t.name for t in mcp_tools]})

        # No tools used
        assistant_text = msg.get("content") or ""
        print(f"No tools used - AI chose not to call any tools")
        print(f"Assistant text: '{assistant_text}'")
        print(f"Available tools were: {[t['function']['name'] for t in oai_tools]}")
        messages.append({"role": "assistant", "content": assistant_text})
        SESSIONS[session_id] = messages
        return JSONResponse({"reply": assistant_text, "tools": [t.name for t in mcp_tools]})

    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
    finally:
        if stack:
            with contextlib.suppress(Exception):
                await stack.aclose()
