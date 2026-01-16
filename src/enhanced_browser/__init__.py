"""Enhanced browser tool with dual implementation support.

This module provides browser automation with two implementations:
- LocalChromiumBrowser: Local Playwright-based browser
- AgentCoreBrowser: AWS Bedrock AgentCore cloud browser via CDP

Browser selection is controlled by BROWSER_TYPE environment variable:
- "local" (default): Use LocalChromiumBrowser for local development
- "agentcore": Use AgentCoreBrowser for AWS deployment
"""

import logging
import os

from .browser import Browser, BrowserSession
from .local_chromium_browser import LocalChromiumBrowser
from .agent_core_browser import AgentCoreBrowser

logger = logging.getLogger(__name__)


def create_browser() -> Browser:
    """
    Factory function to create the appropriate browser based on environment.

    Environment variables:
    - BROWSER_TYPE: "local" (default) or "agentcore"

    Returns:
        Browser instance (LocalChromiumBrowser or AgentCoreBrowser)
    """
    browser_type = os.environ.get("BROWSER_TYPE", "local").lower()

    if browser_type == "agentcore":
        logger.info("Creating AgentCoreBrowser (BROWSER_TYPE=agentcore)")
        return AgentCoreBrowser()
    else:
        logger.info(f"Creating LocalChromiumBrowser (BROWSER_TYPE={browser_type})")
        return LocalChromiumBrowser()


# Backward compatibility alias (deprecated - use create_browser() instead)
EnhancedLocalChromiumBrowser = LocalChromiumBrowser

__all__ = [
    "Browser",
    "BrowserSession",
    "LocalChromiumBrowser",
    "AgentCoreBrowser",
    "EnhancedLocalChromiumBrowser",
    "create_browser",
]