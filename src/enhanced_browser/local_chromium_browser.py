"""
Local Chromium Browser implementation using Playwright.

This module provides a local browser implementation that launches
Chromium directly on the host machine using Playwright.
"""

import logging
import os

from playwright.async_api import Browser as PlaywrightBrowser

from .browser import Browser
from .models import InitSessionAction

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LocalChromiumBrowser(Browser):
    """
    Local Playwright Chromium browser implementation.

    This implementation launches a local Chromium browser instance
    using Playwright. Supports both headless and headed modes with
    configurable viewport and slow motion for debugging.

    Configuration is read from config.py with environment variable overrides:
    - STRANDS_BROWSER_HEADLESS: "true"/"false" (default from config)
    - STRANDS_BROWSER_WIDTH: viewport width in pixels (default from config)
    - STRANDS_BROWSER_HEIGHT: viewport height in pixels (default from config)
    - STRANDS_BROWSER_SLOW_MO: delay between actions in ms (default 100 if headed, 0 if headless)

    Example:
        browser = LocalChromiumBrowser()
        browser.browser(browser_input={
            "action": {
                "type": "init_session",
                "session_name": "my-session",
                "description": "Local browser session"
            }
        })
    """

    def start_platform(self) -> None:
        """
        Platform-specific startup logic.

        No additional startup needed for local Chromium - Playwright
        handles browser binary management automatically.
        """
        pass

    def close_platform(self) -> None:
        """
        Platform-specific cleanup logic.

        No additional cleanup needed for local Chromium - browser
        instances are closed via session management in the base class.
        """
        pass

    async def create_browser_session(self, action: InitSessionAction) -> PlaywrightBrowser:
        """
        Launch a local Chromium browser instance.

        Reads configuration from config.py with environment variable overrides
        and launches Chromium using Playwright.

        Args:
            action: InitSessionAction with session configuration

        Returns:
            PlaywrightBrowser instance connected to local Chromium
        """
        # Import config here to avoid circular imports
        from config import config as browser_config

        # Read configuration from config.py with environment variable overrides
        headless = (
            os.getenv(
                "STRANDS_BROWSER_HEADLESS", str(browser_config.browser.headless).lower()
            ).lower()
            == "true"
        )
        width = int(
            os.getenv("STRANDS_BROWSER_WIDTH", str(browser_config.browser.width))
        )
        height = int(
            os.getenv("STRANDS_BROWSER_HEIGHT", str(browser_config.browser.height))
        )

        # Launch browser with slow_mo for debugging if not headless
        slow_mo = int(
            os.getenv("STRANDS_BROWSER_SLOW_MO", "100" if not headless else "0")
        )

        logger.info(
            f"Launching local Chromium: headless={headless}, "
            f"viewport={width}x{height}, slow_mo={slow_mo}ms"
        )

        browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[f"--window-size={width},{height}"],
            slow_mo=slow_mo,
        )

        return browser
