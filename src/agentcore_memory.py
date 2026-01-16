"""AgentCore episodic memory integration for the airline check-in agent.

This module provides utilities for:
1. Creating session managers for Strands agent integration
2. URL slugification for actor IDs

Setup:
    Run `python scripts/create_agentcore_memory.py` once to create the memory store,
    then set AGENTCORE_MEMORY_ID in your .env file.
"""

import logging
import re

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

from config import config

logger = logging.getLogger(__name__)


def slugify_url(url: str) -> str:
    """Convert URL to a safe actor ID.

    Examples:
        https://example.com/path -> example-com-path
        http://localhost:8001/ -> localhost-8001
    """
    # Remove protocol
    slug = re.sub(r"^https?://", "", url)
    # Remove trailing slash
    slug = slug.rstrip("/")
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def create_session_manager(
    memory_id: str,
    actor_id: str,
    session_id: str,
    region: str,
) -> AgentCoreMemorySessionManager:
    """Create a session manager for Strands agent integration.

    Args:
        memory_id: The AgentCore memory store ID
        actor_id: Actor identifier (typically slugified URL)
        session_id: Unique session identifier
        region: AWS region for AgentCore

    Returns:
        Configured AgentCoreMemorySessionManager
    """
    # Configure memory
    agentcore_memory_config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        session_id=session_id,
        actor_id=actor_id,
    )

    # Create session manager
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=agentcore_memory_config,
        region_name=region,
    )

    logger.info(
        f"Created session manager - memory: {memory_id}, actor: {actor_id}, session: {session_id}"
    )
    return session_manager


def create_memory_session_manager_for_url(
    url: str,
    session_id: str,
) -> AgentCoreMemorySessionManager:
    """Create a session manager for a URL.

    Requires AGENTCORE_MEMORY_ID to be set in environment.
    Run `python scripts/create_agentcore_memory.py` to create the memory store first.

    Args:
        url: The airline website URL (used to derive actor_id)
        session_id: Unique session identifier

    Returns:
        Configured AgentCoreMemorySessionManager

    Raises:
        ValueError: If AGENTCORE_MEMORY_ID is not set
    """
    memory_id = config.memory.memory_id
    if not memory_id:
        raise ValueError(
            "AGENTCORE_MEMORY_ID not set. "
            "Run `python scripts/create_agentcore_memory.py` to create memory, "
            "then add AGENTCORE_MEMORY_ID=<id> to your .env file."
        )

    region = config.model.region
    actor_id = slugify_url(url)

    return create_session_manager(
        memory_id=memory_id,
        actor_id=actor_id,
        session_id=session_id,
        region=region,
    )
