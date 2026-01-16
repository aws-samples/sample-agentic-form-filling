"""FastAPI server for AgentCore deployment with streaming support.

Reuses create_agent() from agent.py to maintain consistency with local execution.
Memory/learnings are handled by AgentCore episodic memory, which persists
across container invocations.
"""
import os
import sys
import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Force headless mode before any imports
os.environ["STRANDS_BROWSER_HEADLESS"] = "true"

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Import from existing agent.py - reuse the same agent creation logic
from agent import create_agent, build_task_prompt
from config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Airline Check-in Agent", version="1.0.0")


class InvocationRequest(BaseModel):
    input: Dict[str, Any]


@app.get("/ping")
async def ping():
    """Health check endpoint required by AgentCore."""
    return {"status": "healthy"}


AGENTCORE_SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"


@app.post("/invocations")
async def invoke_agent(body: InvocationRequest, request: Request):
    """Streaming invocation endpoint.

    Accepts either:
    - {"prompt": "custom prompt"} - for arbitrary agent tasks
    - {} or {"use_default_task": true} - runs the default check-in task from config

    Session ID is extracted from the X-Amzn-Bedrock-AgentCore-Runtime-Session-Id header
    when running in AgentCore, or generated locally if not provided.
    """
    prompt = body.input.get("prompt")
    use_default = body.input.get("use_default_task", False)

    # If no prompt provided and use_default is true, use configured check-in task
    if not prompt and use_default:
        prompt = build_task_prompt()
    elif not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt' in input (or set use_default_task: true)")

    # Get URL from input or use default
    url = body.input.get("url", config.checkin.airline_url)

    # Extract session ID from AgentCore header (if present)
    session_id = request.headers.get(AGENTCORE_SESSION_HEADER)
    if session_id:
        logger.info(f"Using session ID from AgentCore header: {session_id}")
    else:
        logger.info("No AgentCore session header found - session ID will be generated")

    async def generate():
        browser = None
        try:
            # Create agent with memory integration (episodic memory persists across invocations)
            # Pass session_id from AgentCore header if available
            agent, browser = create_agent(url=url, session_id=session_id)

            # Initialize browser session
            browser.browser(browser_input={
                "action": {
                    "type": "init_session",
                    "session_name": "check-in-session",
                    "description": "AgentCore invocation"
                }
            })

            # Stream the agent response (don't log prompt - may contain credentials)
            logger.info("Starting agent task execution...")
            async for event in agent.stream_async(prompt):
                if "data" in event:
                    yield event["data"]

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            yield f"Error: {str(e)}"
        finally:
            # Cleanup browser
            if browser:
                try:
                    browser.browser(browser_input={
                        "action": {"type": "close", "session_name": "check-in-session"}
                    })
                except Exception:
                    pass

    return StreamingResponse(generate(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    # Use asyncio loop instead of uvloop to avoid conflict with nest_asyncio in browser code
    uvicorn.run(app, host="0.0.0.0", port=8080, loop="asyncio")
