"""
AgentCore Browser implementation using AWS Bedrock AgentCore via CDP.

This module provides a cloud browser implementation that connects to
AWS Bedrock AgentCore browser service using Chrome DevTools Protocol (CDP).
"""

import logging
import os
from typing import Any, Dict

from playwright.async_api import Browser as PlaywrightBrowser

from .browser import Browser, BrowserSession
from .cloudfront_signer import extract_cloudfront_domain, get_signer_from_env
from .models import InitSessionAction

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AgentCoreBrowser(Browser):
    """
    AWS Bedrock AgentCore cloud browser implementation via CDP.

    This implementation connects to AgentCore's managed browser service
    using Chrome DevTools Protocol. The browser runs in AWS infrastructure,
    providing scalable, serverless browser automation.

    Configuration:
    - region: AWS region for AgentCore (default from AWS_REGION env var or us-west-2)
    - identifier: AgentCore browser identifier (default: "aws.browser.v1")
    - session_timeout: Browser session timeout in seconds (default: 3600)

    Example:
        browser = AgentCoreBrowser(region="us-west-2")
        browser.browser(browser_input={
            "action": {
                "type": "init_session",
                "session_name": "my-session",
                "description": "AgentCore browser session"
            }
        })
    """

    def __init__(
        self,
        region: str = None,
        identifier: str = "aws.browser.v1",
        session_timeout: int = 3600,
    ):
        """
        Initialize AgentCore browser.

        Args:
            region: AWS region for AgentCore service. Defaults to AWS_REGION
                   environment variable or us-west-2.
            identifier: AgentCore browser identifier. Defaults to "aws.browser.v1".
            session_timeout: Browser session timeout in seconds. Defaults to 3600 (1 hour).
        """
        super().__init__()
        self._region = region or os.environ.get("AWS_REGION", "us-west-2")
        self._identifier = identifier
        self._session_timeout = session_timeout
        self._client_dict: Dict[str, Any] = {}  # session_name -> AgentCoreBrowserClient

        logger.info(
            f"AgentCoreBrowser initialized: region={self._region}, "
            f"identifier={self._identifier}, timeout={self._session_timeout}s"
        )

    def start_platform(self) -> None:
        """
        Platform-specific startup logic.

        AgentCore browsers are created on-demand during session initialization,
        so no platform-wide startup is needed.
        """
        pass

    def close_platform(self) -> None:
        """
        Platform-specific cleanup logic.

        Stops all AgentCore browser clients to release cloud resources.
        """
        for session_name, client in list(self._client_dict.items()):
            try:
                logger.info(f"Stopping AgentCore client for session '{session_name}'")
                client.stop()
            except Exception as e:
                logger.warning(f"Error stopping AgentCore client '{session_name}': {e}")
        self._client_dict.clear()

    async def create_browser_session(self, action: InitSessionAction) -> PlaywrightBrowser:
        """
        Connect to AgentCore browser via CDP.

        Creates a new AgentCore browser session and connects to it using
        Chrome DevTools Protocol over WebSocket.

        Args:
            action: InitSessionAction with session configuration

        Returns:
            PlaywrightBrowser instance connected to AgentCore via CDP
        """
        # Import here to avoid import errors if bedrock_agentcore not installed
        try:
            from bedrock_agentcore.tools.browser_client import BrowserClient
        except ImportError as e:
            raise ImportError(
                f"Failed to import BrowserClient from bedrock_agentcore: {e}. "
                "Ensure bedrock-agentcore is installed: pip install bedrock-agentcore"
            ) from e

        logger.info(
            f"Creating AgentCore browser session: region={self._region}, "
            f"identifier={self._identifier}, timeout={self._session_timeout}s"
        )

        # Create and start AgentCore client
        client = BrowserClient(region=self._region)
        session_id = client.start(
            identifier=self._identifier,
            session_timeout_seconds=self._session_timeout
        )
        logger.info(f"AgentCore session started: {session_id}")

        # Store client for cleanup
        self._client_dict[action.session_name] = client

        # Get CDP connection details
        cdp_url, cdp_headers = client.generate_ws_headers()
        logger.info(f"Connecting to AgentCore via CDP: {cdp_url[:50]}...")

        # Connect via CDP
        browser = await self._playwright.chromium.connect_over_cdp(
            endpoint_url=cdp_url,
            headers=cdp_headers
        )

        logger.info("Successfully connected to AgentCore browser via CDP")
        return browser

    async def _setup_session_from_browser(
        self, action: InitSessionAction, browser: PlaywrightBrowser
    ) -> Dict[str, Any]:
        """
        Setup session from AgentCore browser.

        AgentCore provides a pre-existing browser context via CDP,
        so we reuse it instead of creating a new one.

        Args:
            action: InitSessionAction with session configuration
            browser: PlaywrightBrowser connected via CDP

        Returns:
            Success/error response dict
        """
        # Import config here to avoid circular imports
        from config import config as browser_config

        width = int(os.getenv("STRANDS_BROWSER_WIDTH", str(browser_config.browser.width)))
        height = int(os.getenv("STRANDS_BROWSER_HEIGHT", str(browser_config.browser.height)))

        # AgentCore provides existing context(s) via CDP - reuse if available
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
            logger.info("Reusing existing AgentCore browser context")
        else:
            # Fallback: create new context if none exists
            context = await browser.new_context(
                viewport={"width": width, "height": height}
            )
            logger.info(f"Created new browser context: {width}x{height}")

        # Add CloudFront signed cookies if configured
        signer = get_signer_from_env()
        if signer and action.url:
            cloudfront_domain = extract_cloudfront_domain(action.url)
            if cloudfront_domain:
                cookies = signer.get_playwright_cookies(cloudfront_domain)
                await context.add_cookies(cookies)
                logger.info(f"Added CloudFront signed cookies for {cloudfront_domain}")

        # Get or create page
        pages = context.pages
        if pages:
            page = pages[0]
            logger.info("Reusing existing AgentCore page")
        else:
            page = await context.new_page()
            logger.info("Created new page in context")

        # Create session
        session = BrowserSession(
            session_name=action.session_name,
            description=action.description,
            browser=browser,
            page=page,
        )
        self._sessions[action.session_name] = session

        logger.info(f"AgentCore session '{action.session_name}' initialized")

        return {
            "status": "success",
            "content": [
                {
                    "json": {
                        "sessionName": action.session_name,
                        "description": action.description,
                        "platform": "agentcore",
                        "region": self._region,
                    }
                }
            ],
        }

    async def _async_close(self, action) -> Dict[str, Any]:
        """
        Close session and cleanup AgentCore client.

        Overrides base class to also stop the AgentCore client
        and release cloud resources.

        Args:
            action: CloseAction with session name

        Returns:
            Success/error response dict
        """
        session = self._sessions.get(action.session_name)
        if not session:
            return {
                "status": "error",
                "content": [{"text": f"Session '{action.session_name}' not found"}],
            }

        try:
            # Close browser session
            await session.close()
            del self._sessions[action.session_name]

            # Stop AgentCore client
            client = self._client_dict.pop(action.session_name, None)
            if client:
                try:
                    client.stop()
                    logger.info(f"AgentCore client stopped for session '{action.session_name}'")
                except Exception as e:
                    logger.warning(f"Error stopping AgentCore client: {e}")

            return {"status": "success", "content": [{"text": "Session closed"}]}
        except Exception as e:
            return {"status": "error", "content": [{"text": f"Close failed: {str(e)}"}]}

    def __del__(self):
        """Cleanup on destruction."""
        try:
            # Close all sessions
            for session in list(self._sessions.values()):
                self._execute_async(session.close())

            # Stop all AgentCore clients
            self.close_platform()

            # Stop Playwright
            if self._playwright:
                self._execute_async(self._playwright.stop())
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")
