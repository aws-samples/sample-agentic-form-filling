#!/usr/bin/env python3
"""
Airline check-in automation agent.

Uses a minimal system prompt with essential context, letting the LLM
figure out the best approach. Relies on tool descriptions and reasoning
rather than detailed directives.
"""

import datetime
import logging
import os
import sys
import time
from pathlib import Path

from opentelemetry import baggage, context

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from strands import Agent
from strands.models import BedrockModel
from strands.types.content import SystemContentBlock
from config import config
from enhanced_browser import Browser, create_browser
from image_filtering_conversation_manager import ImageFilteringConversationManager
from agentcore_memory import create_memory_session_manager_for_url, slugify_url

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def build_system_prompt() -> list[SystemContentBlock]:
    """
    Build a minimal system prompt - just role and speed requirement.

    Memory/learnings are now handled by AgentCore episodic memory,
    which automatically retrieves relevant past episodes and reflections.

    Returns:
        List of SystemContentBlock with cache point
    """
    system_text = """<role>
You are a browser automation agent. Complete tasks quickly and efficiently.
Use the browser tool to navigate, inspect elements, and interact with web pages.
Session name: "check-in-session"
</role>

<speed>
CRITICAL: Execute fast. Minimize tool calls. Combine actions into lists when possible.
</speed>"""

    logger.info(f"System prompt:\n{system_text}")
    return [
        SystemContentBlock(text=system_text),
        SystemContentBlock(cachePoint={"type": "default"})
    ]


def create_agent(url: str, session_id: str | None = None) -> tuple[Agent, Browser]:
    """
    Create the agent with browser tools and AgentCore memory.

    Args:
        url: The airline website URL (used for actor_id in memory)
        session_id: Optional session ID (from AgentCore header or generated)

    Returns:
        Tuple of (Configured Agent instance, Browser instance)
    """
    model = BedrockModel(
        model_id=config.model.model_id,
        temperature=config.model.temperature,
        max_tokens=config.model.max_tokens,
        streaming=True,
        cache_tools="default"
    )

    browser = create_browser()
    system_prompt = build_system_prompt()

    # Create session manager based on memory configuration
    session_manager = None
    if config.memory.enabled:
        # Use provided session ID or generate one
        if not session_id:
            session_id = f"checkin-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        actor_id = slugify_url(url)
        logger.info("=" * 40)
        logger.info("AgentCore Memory Configuration:")
        logger.info(f"  Memory ID: {config.memory.memory_id}")
        logger.info(f"  Actor ID:  {actor_id}")
        logger.info(f"  Session:   {session_id}")
        logger.info(f"  Region:    {config.model.region}")
        logger.info("=" * 40)
        
        # Set session ID in OpenTelemetry baggage for trace correlation
        ctx = baggage.set_baggage("session.id", session_id)
        context.attach(ctx)
        logger.info(f"OpenTelemetry session.id baggage set: {session_id}")
        
        session_manager = create_memory_session_manager_for_url(
            url=url,
            session_id=session_id,
        )
    else:
        # Fallback to image filtering conversation manager when memory is disabled
        session_manager = ImageFilteringConversationManager(
            window_size=8,
            should_truncate_results=False,
            max_images=1
        )
        logger.info("AgentCore memory DISABLED - using ImageFilteringConversationManager")

    tools = [browser.browser]

    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        record_direct_tool_call=False,
        session_manager=session_manager,
        callback_handler=None
    )

    logger.info(f"Agent created with model: {config.model.model_id}")
    return agent, browser


def build_task_prompt() -> str:
    """Build a concise task prompt."""
    return f"""Complete airline check-in and download the boarding pass:
URL: {config.checkin.airline_url}
Login: {config.checkin.login} / {config.checkin.code}
Seat: {config.checkin.seat_preference}

Go fast."""


def run_check_in() -> dict:
    """Run the check-in agent."""
    start_time = time.time()

    try:
        logger.info("=" * 60)
        logger.info("AIRLINE CHECK-IN AGENT")
        logger.info("=" * 60)
        logger.info(f"Target URL: {config.checkin.airline_url}")
        logger.info(f"AgentCore Memory: {'enabled' if config.memory.enabled else 'DISABLED'}")
        logger.info("=" * 60)

        # Create agent with memory integration
        agent, browser = create_agent(url=config.checkin.airline_url)

        # Initialize browser session
        logger.info("Initializing browser...")
        browser.browser(browser_input={
            "action": {
                "type": "init_session",
                "session_name": "check-in-session",
                "description": "Check-in automation"
            }
        })

        # Navigate and get initial state
        logger.info("Navigating to target...")
        nav_result = browser.browser(browser_input={
            "action": [
                {"type": "navigate", "session_name": "check-in-session", "url": config.checkin.airline_url},
                {"type": "get_accessibility_tree", "session_name": "check-in-session"}
            ]
        })

        # Extract accessibility tree
        initial_context = ""
        if nav_result and "content" in nav_result:
            for block in nav_result["content"]:
                if isinstance(block, dict) and "text" in block:
                    text = block["text"]
                    if any(role in text.lower() for role in ["button", "textbox", "link"]):
                        initial_context = text
                        break

        # Execute
        logger.info("Starting check-in...")
        prompt = build_task_prompt()

        if initial_context:
            result = agent(f"Page elements:\n{initial_context}\n\n{prompt}")
        else:
            result = agent(prompt)

        execution_time = time.time() - start_time

        # Log metrics
        if hasattr(result, 'metrics') and result.metrics:
            usage = result.metrics.accumulated_usage
            logger.info(f"Tokens - Input: {usage.get('inputTokens', 0)}, "
                       f"Cache read: {usage.get('cacheReadInputTokens', 0)}, "
                       f"Cache write: {usage.get('cacheWriteInputTokens', 0)}")

        logger.info("=" * 60)
        logger.info(f"COMPLETED in {execution_time:.2f}s")
        logger.info(f"Result: {result.message}")
        logger.info("=" * 60)

        # Note: With AgentCore episodic memory, learnings are automatically
        # captured as episodes and reflections - no manual save needed

        return {
            "status": "success",
            "execution_time": execution_time,
            "result": result.message,
            "target_met": execution_time < 60,
        }

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Failed after {execution_time:.2f}s: {e}")
        return {
            "status": "error",
            "execution_time": execution_time,
            "error": str(e),
            "target_met": False,
        }


def main():
    """Main entry point."""
    result = run_check_in()

    print("\n" + "=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Status: {result['status'].upper()}")
    print(f"Time: {result['execution_time']:.2f}s")
    print(f"Target (<60s): {'YES' if result['target_met'] else 'NO'}")

    if result["status"] == "error":
        print(f"Error: {result['error']}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
