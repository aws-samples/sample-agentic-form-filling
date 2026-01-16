"""
Abstract Browser base class for browser automation.

This module provides the common infrastructure for browser automation with:
- Action list execution (multiple actions in a single call)
- Accessibility tree extraction with embedding-based filtering
- HTML semantic filtering
- CloudFront signed cookie injection

Implementations:
- LocalChromiumBrowser: Local Playwright-based browser
- AgentCoreBrowser: AWS Bedrock AgentCore cloud browser via CDP
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import nest_asyncio
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from strands import tool

from .accessibility_tree import AccessibilityTreeExtractor, ChunkingStrategy, HtmlSemanticFilter
from .cloudfront_signer import CloudFrontSigner, extract_cloudfront_domain, get_signer_from_env
from .models import (
    ClickAction,
    CloseAction,
    EnhancedBrowserInput,
    EvaluateJsAction,
    GetAccessibilityTreeAction,
    GetHtmlAction,
    GetTextAction,
    HoverAction,
    InitSessionAction,
    KeyPressAction,
    NavigateAction,
    ScreenshotAction,
    ScrollAction,
    ScrollToBottomAction,
    ScrollToTopAction,
    TypeAction,
    WaitAction,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BrowserSession:
    """Browser session management."""

    def __init__(
        self,
        session_name: str,
        description: str,
        browser: PlaywrightBrowser,
        page: Page,
    ):
        self.session_name = session_name
        self.description = description
        self.browser = browser
        self.page = page

    async def close(self):
        """Close the session."""
        try:
            await self.browser.close()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


class Browser(ABC):
    """Abstract base class for browser automation with enhanced features."""

    def __init__(self):
        """Initialize the browser with common infrastructure."""
        self._started = False
        self._playwright = None
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._nest_asyncio_applied = False
        self._sessions: Dict[str, BrowserSession] = {}
        self._accessibility_extractor = AccessibilityTreeExtractor()
        self._html_filter = HtmlSemanticFilter()

    @abstractmethod
    async def create_browser_session(self, action: InitSessionAction) -> PlaywrightBrowser:
        """
        Create a browser instance for a new session.

        Platform-specific implementation:
        - LocalChromiumBrowser: Launch local Chromium
        - AgentCoreBrowser: Connect via CDP to AgentCore

        Args:
            action: InitSessionAction with session configuration

        Returns:
            PlaywrightBrowser instance
        """
        pass

    @abstractmethod
    def start_platform(self) -> None:
        """Platform-specific startup logic."""
        pass

    @abstractmethod
    def close_platform(self) -> None:
        """Platform-specific cleanup logic."""
        pass

    @tool
    def browser(self, browser_input: EnhancedBrowserInput) -> Dict[str, Any]:
        """
        Enhanced browser automation tool with action lists and accessibility tree (A11y Tree) support.

        CRITICAL: The input MUST be structured as: {"action": {...}} or {"action": [...]}
        Pass a single action object OR a list of actions to execute in sequence.

        Example init_session:
        {"action": {"type": "init_session", "session_name": "my-session", "description": "..."}}

        Example navigate:
        {"action": {"type": "navigate", "session_name": "my-session", "url": "https://example.com"}}

        Example screenshot:
        {"action": {"type": "screenshot", "session_name": "my-session"}}

        Example click by coordinates (USE THIS when you can see the element in a screenshot):
        {"action": {"type": "click", "session_name": "my-session", "x": 640, "y": 400}}

        Example click by selector (only when you know the CSS selector):
        {"action": {"type": "click", "session_name": "my-session", "selector": "button#submit"}}

        Example type text into an input field:
        {"action": {"type": "type", "session_name": "my-session", "selector": "input#email", "text": "user@example.com"}}

        Example scroll down to see more content:
        {"action": {"type": "scroll", "session_name": "my-session", "y": 500}}

        Example scroll to top of page:
        {"action": {"type": "scroll_to_top", "session_name": "my-session"}}

        Example scroll to bottom of page:
        {"action": {"type": "scroll_to_bottom", "session_name": "my-session"}}

        Example hover over coordinates (verify position or trigger hover states):
        {"action": {"type": "hover", "session_name": "my-session", "x": 640, "y": 400}}

        Example wait for element:
        {"action": {"type": "wait", "session_name": "my-session", "selector": "button#submit", "timeout": 5000}}

        Example get text from element:
        {"action": {"type": "get_text", "session_name": "my-session", "selector": "h1.title"}}

        Example get HTML content:
        {"action": {"type": "get_html", "session_name": "my-session", "selector": "div.content"}}

        Example get_html with SEMANTIC FILTERING (find HTML elements by meaning):
        {"action": {"type": "get_html", "session_name": "my-session", "query": "login form"}}
        Returns: HTML elements ranked by similarity to your query with percentage scores

        Example get_html with custom threshold:
        {"action": {"type": "get_html", "session_name": "my-session", "query": "submit button", "similarity_threshold": 0.5}}

        Example LIST OF ACTIONS (execute multiple actions in sequence - PREFERRED):
        {"action": [
            {"type": "navigate", "session_name": "my-session", "url": "https://example.com"},
            {"type": "screenshot", "session_name": "my-session"}
        ]}

        Example click + screenshot:
        {"action": [
            {"type": "click", "session_name": "my-session", "x": 640, "y": 400},
            {"type": "screenshot", "session_name": "my-session"}
        ]}

        Example form fill + submit:
        {"action": [
            {"type": "click", "session_name": "my-session", "selector": "input[name='email']"},
            {"type": "type", "session_name": "my-session", "selector": "input[name='email']", "text": "user@example.com"},
            {"type": "click", "session_name": "my-session", "selector": "button[type='submit']"},
            {"type": "screenshot", "session_name": "my-session"}
        ]}

        Example key press (Enter key):
        {"action": {"type": "key_press", "session_name": "my-session", "key": "Enter"}}

        Example key press with focus:
        {"action": {"type": "key_press", "session_name": "my-session", "key": "Enter", "selector": "input[name='search']"}}

        Example evaluate_js (click element by selector when coordinates miss):
        {"action": {"type": "evaluate_js", "session_name": "my-session", "script": "document.querySelector('button.submit').click()"}}

        Example evaluate_js (get bounding box and center coordinates for precise clicking):
        {"action": {"type": "evaluate_js", "session_name": "my-session", "script": "const el = document.querySelector('button.submit'); const rect = el.getBoundingClientRect(); ({x: rect.x, y: rect.y, width: rect.width, height: rect.height, centerX: rect.x + rect.width/2, centerY: rect.y + rect.height/2})"}}
        Returns: {x, y, width, height, centerX, centerY} - use centerX/centerY for click coordinates!

        Example evaluate_js (get all clickable elements with positions):
        {"action": {"type": "evaluate_js", "session_name": "my-session", "script": "Array.from(document.querySelectorAll('button, a, [role=button]')).map(el => { const r = el.getBoundingClientRect(); return {text: el.textContent.trim().slice(0,30), centerX: Math.round(r.x + r.width/2), centerY: Math.round(r.y + r.height/2)} })"}}

        Example evaluate_js (fill input field directly):
        {"action": {"type": "evaluate_js", "session_name": "my-session", "script": "document.querySelector('input[name=email]').value = 'user@example.com'"}}

        Example get_accessibility_tree (DISCOVER all clickable elements when you can't find them visually):
        {"action": {"type": "get_accessibility_tree", "session_name": "my-session"}}
        Returns: list of buttons, links, inputs, checkboxes with their labels - use this to find click targets!

        Example get_accessibility_tree with SEMANTIC FILTERING (find elements by meaning):
        {"action": {"type": "get_accessibility_tree", "session_name": "my-session", "query": "submit button"}}
        Returns: elements ranked by similarity to your query with percentage scores

        Example get_accessibility_tree with custom threshold and subtree chunking:
        {"action": {"type": "get_accessibility_tree", "session_name": "my-session", "query": "login form", "similarity_threshold": 0.5, "chunking_strategy": "subtrees"}}

        Example get_accessibility_tree with STATE FILTERING (find available seats - exclude disabled):
        {"action": {"type": "get_accessibility_tree", "session_name": "my-session", "filter_roles": ["button"], "filter_states": ["-disabled"]}}
        Returns: only enabled (clickable) buttons - perfect for finding available seats!

        Example get_accessibility_tree with ROLE FILTERING (find only buttons):
        {"action": {"type": "get_accessibility_tree", "session_name": "my-session", "filter_roles": ["button"]}}

        Example combining state filter with semantic query:
        {"action": {"type": "get_accessibility_tree", "session_name": "my-session", "query": "seat row 10", "filter_states": ["-disabled"]}}
        Returns: available seats matching "row 10" ranked by similarity

        Example close session:
        {"action": {"type": "close", "session_name": "my-session"}}

        Available action types: init_session, navigate, click, type, key_press, get_text,
        get_html, screenshot, wait, scroll, scroll_to_top, scroll_to_bottom, hover, evaluate_js, close, get_accessibility_tree

        NOTE: Pass a list of actions for sequential execution (preferred for efficiency).

        Args:
            browser_input: Structured input with "action" field containing the action to perform

        Returns:
            Dict containing execution results with "status" (success/error) and "content"
        """
        # Auto-start on first use
        if not self._started:
            self._start()

        if isinstance(browser_input, dict):
            logger.debug(f"Action passed as Dict: {browser_input}")
            try:
                validated_input = EnhancedBrowserInput.model_validate(browser_input)
                action = validated_input.action
                # Check if action is a list (new direct list support)
                if isinstance(action, list):
                    logger.debug(f"Action is a list of {len(action)} actions - executing sequentially")
                else:
                    logger.debug(f"Successfully validated action type: {action.type}")
            except Exception as e:
                logger.error(f"Failed to validate browser input: {e}")
                logger.error(f"Input was: {browser_input}")
                raise
        else:
            action = browser_input.action
            logger.debug(f"Action passed as object: {action}")

        # Handle list of actions (new direct list support)
        if isinstance(action, list):
            logger.info(f"Processing action list with {len(action)} actions")
            return self._execute_action_list(action)

        logger.info(f"Processing browser action: {type(action).__name__} with type={getattr(action, 'type', 'unknown')}")

        # Route to appropriate handler
        if isinstance(action, InitSessionAction):
            return self.init_session(action)
        elif isinstance(action, NavigateAction):
            return self.navigate(action)
        elif isinstance(action, ClickAction):
            return self.click(action)
        elif isinstance(action, TypeAction):
            return self.type_text(action)
        elif isinstance(action, KeyPressAction):
            return self.key_press(action)
        elif isinstance(action, GetTextAction):
            return self.get_text(action)
        elif isinstance(action, GetHtmlAction):
            return self.get_html(action)
        elif isinstance(action, ScreenshotAction):
            return self.screenshot(action)
        elif isinstance(action, WaitAction):
            return self.wait(action)
        elif isinstance(action, ScrollAction):
            return self.scroll(action)
        elif isinstance(action, HoverAction):
            return self.hover(action)
        elif isinstance(action, ScrollToTopAction):
            return self.scroll_to_top(action)
        elif isinstance(action, ScrollToBottomAction):
            return self.scroll_to_bottom(action)
        elif isinstance(action, EvaluateJsAction):
            return self.evaluate_js(action)
        elif isinstance(action, GetAccessibilityTreeAction):
            return self.get_accessibility_tree(action)
        elif isinstance(action, CloseAction):
            return self.close(action)
        else:
            return {
                "status": "error",
                "content": [{"text": f"Unknown action type: {type(action)}"}],
            }

    def _start(self) -> None:
        """Start Playwright and initialize platform."""
        if not self._started:
            self._playwright = self._execute_async(async_playwright().start())
            self.start_platform()
            self._started = True
            logger.info("Playwright initialized")

    def _execute_async(self, action_coro) -> Any:
        """Execute async coroutine in the event loop."""
        if not self._nest_asyncio_applied:
            nest_asyncio.apply()
            self._nest_asyncio_applied = True

        return self._loop.run_until_complete(action_coro)

    def validate_session(self, session_name: str) -> Optional[Dict[str, Any]]:
        """Validate that a session exists."""
        if session_name not in self._sessions:
            return {
                "status": "error",
                "content": [{"text": f"Session '{session_name}' not found"}],
            }
        return None

    def get_session_page(self, session_name: str) -> Optional[Page]:
        """Get the page for a session."""
        session = self._sessions.get(session_name)
        return session.page if session else None

    # Session Management
    def init_session(self, action: InitSessionAction) -> Dict[str, Any]:
        """Initialize a new browser session."""
        return self._execute_async(self._async_init_session(action))

    async def _async_init_session(self, action: InitSessionAction) -> Dict[str, Any]:
        """Async init session implementation."""
        logger.info(f"Initializing browser session: {action.description}")

        if action.session_name in self._sessions:
            return {
                "status": "error",
                "content": [{"text": f"Session '{action.session_name}' already exists"}],
            }

        try:
            # Create browser via platform-specific implementation
            browser = await self.create_browser_session(action)

            # Setup session from browser (common logic)
            return await self._setup_session_from_browser(action, browser)

        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            return {"status": "error", "content": [{"text": f"Failed: {str(e)}"}]}

    async def _setup_session_from_browser(
        self, action: InitSessionAction, browser: PlaywrightBrowser
    ) -> Dict[str, Any]:
        """
        Common session setup after browser creation.

        Can be overridden by implementations that need different context handling
        (e.g., AgentCoreBrowser reuses existing CDP context).
        """
        # Import config here to avoid circular imports
        from config import config as browser_config

        width = int(os.getenv("STRANDS_BROWSER_WIDTH", str(browser_config.browser.width)))
        height = int(os.getenv("STRANDS_BROWSER_HEIGHT", str(browser_config.browser.height)))
        headless = os.getenv("STRANDS_BROWSER_HEADLESS", str(browser_config.browser.headless).lower()).lower() == "true"

        # Create context and page
        context = await browser.new_context(
            viewport={"width": width, "height": height}
        )

        # Add CloudFront signed cookies if configured
        signer = get_signer_from_env()
        if signer and action.url:
            cloudfront_domain = extract_cloudfront_domain(action.url)
            if cloudfront_domain:
                cookies = signer.get_playwright_cookies(cloudfront_domain)
                await context.add_cookies(cookies)
                logger.info(f"Added CloudFront signed cookies for {cloudfront_domain}")

        page = await context.new_page()

        # Enable mouse cursor tracking for debugging (only works in headed mode)
        if not headless:
            await page.evaluate("""
                document.addEventListener('mousemove', (e) => {
                    let cursor = document.getElementById('playwright-cursor');
                    if (!cursor) {
                        cursor = document.createElement('div');
                        cursor.id = 'playwright-cursor';
                        cursor.style.cssText = `
                            position: fixed;
                            width: 20px;
                            height: 20px;
                            border: 3px solid red;
                            border-radius: 50%;
                            pointer-events: none;
                            z-index: 999999;
                            transform: translate(-50%, -50%);
                        `;
                        document.body.appendChild(cursor);
                    }
                    cursor.style.left = e.clientX + 'px';
                    cursor.style.top = e.clientY + 'px';
                });
            """)

        # Create session
        session = BrowserSession(
            session_name=action.session_name,
            description=action.description,
            browser=browser,
            page=page,
        )
        self._sessions[action.session_name] = session

        logger.info(f"Session '{action.session_name}' initialized")

        return {
            "status": "success",
            "content": [
                {
                    "json": {
                        "sessionName": action.session_name,
                        "description": action.description,
                    }
                }
            ],
        }

    # Navigation Actions
    def navigate(self, action: NavigateAction) -> Dict[str, Any]:
        """Navigate to a URL."""
        return self._execute_async(self._async_navigate(action))

    async def _async_navigate(self, action: NavigateAction) -> Dict[str, Any]:
        """Async navigate implementation."""
        logger.debug(f"Navigate action: session={action.session_name}, url={action.url}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Navigate validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Navigate failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            cloudfront_domain = extract_cloudfront_domain(action.url)
            if cloudfront_domain:
                signer = get_signer_from_env()
                if signer:
                    cookies = signer.get_playwright_cookies(cloudfront_domain)
                    await page.context.add_cookies(cookies)
                    logger.info(f"Added CloudFront signed cookies for {cloudfront_domain}")

            logger.debug(f"Starting navigation to: {action.url}")
            await page.goto(action.url)
            await page.wait_for_load_state("networkidle")
            logger.debug(f"Navigation successful to: {action.url}")
            return {"status": "success", "content": [{"text": f"Navigated to {action.url}"}]}
        except Exception as e:
            logger.error(f"Navigation failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Navigation failed: {str(e)}"}]}

    # Interaction Actions
    def click(self, action: ClickAction) -> Dict[str, Any]:
        """Click on an element."""
        return self._execute_async(self._async_click(action))

    async def _async_click(self, action: ClickAction) -> Dict[str, Any]:
        """Async click implementation - supports CSS selector and coordinates."""
        logger.debug(f"Click action: session={action.session_name}, selector={action.selector}, x={action.x}, y={action.y}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Click validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Click failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            # Coordinate-based clicking
            if action.x is not None and action.y is not None:
                logger.debug(f"Attempting to click at coordinates: ({action.x}, {action.y})")

                # Move mouse and click
                await page.mouse.click(action.x, action.y)
                logger.debug(f"Click successful at coordinates: ({action.x}, {action.y})")
                return {"status": "success", "content": [{"text": f"Clicked at ({action.x}, {action.y})"}]}

            # CSS selector-based clicking
            elif action.selector:
                logger.debug(f"Attempting to click selector: {action.selector}")
                await page.click(action.selector)
                logger.debug(f"Click successful: {action.selector}")
                return {"status": "success", "content": [{"text": f"Clicked: {action.selector}"}]}

            else:
                logger.error("Click failed: Must provide selector or coordinates")
                return {"status": "error", "content": [{"text": "Must provide selector or coordinates (x, y)"}]}

        except Exception as e:
            logger.error(f"Click failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Click failed: {str(e)}"}]}

    def type_text(self, action: TypeAction) -> Dict[str, Any]:
        """Type text into an element."""
        return self._execute_async(self._async_type_text(action))

    async def _async_type_text(self, action: TypeAction) -> Dict[str, Any]:
        """Async type implementation."""
        logger.debug(f"Type action: session={action.session_name}, selector={action.selector}, text_length={len(action.text)}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Type validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Type failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            logger.debug(f"Attempting to type into: {action.selector}")
            await page.fill(action.selector, action.text)
            logger.debug(f"Type successful into: {action.selector}")
            return {
                "status": "success",
                "content": [{"text": f"Typed into {action.selector}"}],
            }
        except Exception as e:
            logger.error(f"Type failed on {action.selector}: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Type failed: {str(e)}"}]}

    def key_press(self, action: KeyPressAction) -> Dict[str, Any]:
        """Press a keyboard key."""
        return self._execute_async(self._async_key_press(action))

    async def _async_key_press(self, action: KeyPressAction) -> Dict[str, Any]:
        """Async key press implementation."""
        logger.debug(f"Key press action: session={action.session_name}, key={action.key}, selector={action.selector}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Key press validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Key press failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            # If selector provided, focus on element first
            if action.selector:
                logger.debug(f"Focusing on element: {action.selector}")
                await page.focus(action.selector)

            logger.debug(f"Pressing key: {action.key}")
            await page.keyboard.press(action.key)
            logger.debug(f"Key press successful: {action.key}")

            return {
                "status": "success",
                "content": [{"text": f"Pressed key: {action.key}"}],
            }
        except Exception as e:
            logger.error(f"Key press failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Key press failed: {str(e)}"}]}

    def wait(self, action: WaitAction) -> Dict[str, Any]:
        """Wait for a condition or time."""
        return self._execute_async(self._async_wait(action))

    async def _async_wait(self, action: WaitAction) -> Dict[str, Any]:
        """Async wait implementation."""
        error_response = self.validate_session(action.session_name)
        if error_response:
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            if action.selector:
                await page.wait_for_selector(action.selector, timeout=action.timeout)
                return {
                    "status": "success",
                    "content": [{"text": f"Element {action.selector} appeared"}],
                }
            else:
                await asyncio.sleep(action.timeout / 1000)
                return {
                    "status": "success",
                    "content": [{"text": f"Waited {action.timeout}ms"}],
                }
        except PlaywrightTimeoutError:
            return {
                "status": "error",
                "content": [{"text": f"Timeout waiting for {action.selector}"}],
            }
        except Exception as e:
            return {"status": "error", "content": [{"text": f"Wait failed: {str(e)}"}]}

    def scroll(self, action: ScrollAction) -> Dict[str, Any]:
        """Scroll the page."""
        return self._execute_async(self._async_scroll(action))

    async def _async_scroll(self, action: ScrollAction) -> Dict[str, Any]:
        """Async scroll implementation."""
        logger.debug(f"Scroll action: session={action.session_name}, x={action.x}, y={action.y}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Scroll validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Scroll failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            logger.debug(f"Scrolling by x={action.x}, y={action.y}")
            # Use mouse wheel to scroll
            await page.mouse.wheel(action.x, action.y)
            logger.debug(f"Scroll successful: x={action.x}, y={action.y}")
            return {
                "status": "success",
                "content": [{"text": f"Scrolled by ({action.x}, {action.y})"}],
            }
        except Exception as e:
            logger.error(f"Scroll failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Scroll failed: {str(e)}"}]}

    def hover(self, action: HoverAction) -> Dict[str, Any]:
        """Hover over an element."""
        return self._execute_async(self._async_hover(action))

    async def _async_hover(self, action: HoverAction) -> Dict[str, Any]:
        """Async hover implementation."""
        logger.debug(f"Hover action: session={action.session_name}, x={action.x}, y={action.y}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Hover validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Hover failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            logger.debug(f"Hovering at coordinates: ({action.x}, {action.y})")
            await page.mouse.move(action.x, action.y)
            logger.debug(f"Hover successful at coordinates: ({action.x}, {action.y})")
            return {
                "status": "success",
                "content": [{"text": f"Hovered at ({action.x}, {action.y})"}],
            }
        except Exception as e:
            logger.error(f"Hover failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Hover failed: {str(e)}"}]}

    def scroll_to_top(self, action: ScrollToTopAction) -> Dict[str, Any]:
        """Scroll to the top of the page."""
        return self._execute_async(self._async_scroll_to_top(action))

    async def _async_scroll_to_top(self, action: ScrollToTopAction) -> Dict[str, Any]:
        """Async scroll to top implementation."""
        logger.debug(f"Scroll to top action: session={action.session_name}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Scroll to top validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Scroll to top failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            logger.debug("Scrolling to top of page")
            # Use JavaScript to scroll to top
            await page.evaluate("window.scrollTo(0, 0)")
            logger.debug("Scroll to top successful")
            return {
                "status": "success",
                "content": [{"text": "Scrolled to top of page"}],
            }
        except Exception as e:
            logger.error(f"Scroll to top failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Scroll to top failed: {str(e)}"}]}

    def scroll_to_bottom(self, action: ScrollToBottomAction) -> Dict[str, Any]:
        """Scroll to the bottom of the page."""
        return self._execute_async(self._async_scroll_to_bottom(action))

    async def _async_scroll_to_bottom(self, action: ScrollToBottomAction) -> Dict[str, Any]:
        """Async scroll to bottom implementation."""
        logger.debug(f"Scroll to bottom action: session={action.session_name}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Scroll to bottom validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Scroll to bottom failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            logger.debug("Scrolling to bottom of page")
            # Use JavaScript to scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            logger.debug("Scroll to bottom successful")
            return {
                "status": "success",
                "content": [{"text": "Scrolled to bottom of page"}],
            }
        except Exception as e:
            logger.error(f"Scroll to bottom failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Scroll to bottom failed: {str(e)}"}]}

    # JavaScript Evaluation
    def evaluate_js(self, action: EvaluateJsAction) -> Dict[str, Any]:
        """Execute JavaScript in the browser."""
        return self._execute_async(self._async_evaluate_js(action))

    async def _async_evaluate_js(self, action: EvaluateJsAction) -> Dict[str, Any]:
        """Async JavaScript evaluation implementation."""
        logger.debug(f"Evaluate JS: session={action.session_name}, script_length={len(action.script)}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Evaluate JS validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Evaluate JS failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            logger.debug(f"Executing JavaScript: {action.script[:100]}...")
            result = await page.evaluate(action.script)

            # Convert result to string representation
            import json
            if result is None:
                result_str = "null"
            elif isinstance(result, (dict, list)):
                result_str = json.dumps(result, indent=2, default=str)
            else:
                result_str = str(result)

            logger.debug(f"JavaScript executed successfully, result length: {len(result_str)}")
            return {
                "status": "success",
                "content": [{"text": f"JavaScript result:\n{result_str}"}],
            }
        except Exception as e:
            logger.error(f"JavaScript evaluation failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"JavaScript failed: {str(e)}"}]}

    # Content Extraction Actions
    def get_text(self, action: GetTextAction) -> Dict[str, Any]:
        """Get text content from an element."""
        return self._execute_async(self._async_get_text(action))

    async def _async_get_text(self, action: GetTextAction) -> Dict[str, Any]:
        """Async get text implementation."""
        error_response = self.validate_session(action.session_name)
        if error_response:
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            text = await page.text_content(action.selector)
            return {"status": "success", "content": [{"text": f"Text: {text}"}]}
        except Exception as e:
            return {"status": "error", "content": [{"text": f"Get text failed: {str(e)}"}]}

    def get_html(self, action: GetHtmlAction) -> Dict[str, Any]:
        """Get HTML content, optionally filtered by semantic relevance."""
        return self._execute_async(self._async_get_html(action))

    async def _async_get_html(self, action: GetHtmlAction) -> Dict[str, Any]:
        """Async get HTML implementation with optional semantic filtering."""
        logger.debug(
            f"Get HTML: session={action.session_name}, selector={action.selector}, "
            f"query={action.query}, max_results={action.max_results}, "
            f"threshold={action.similarity_threshold}"
        )

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Get HTML validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Get HTML failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            # Get HTML content
            logger.info(f"Extracting HTML content (selector={action.selector})...")
            if action.selector:
                html = await page.inner_html(action.selector)
            else:
                html = await page.content()

            logger.info(f"HTML extracted: {len(html)} chars")

            # If query provided, use semantic filtering
            if action.query:
                logger.info(f"Applying semantic filter with query: {action.query!r}")
                filtered_result = await self._html_filter.filter_html_semantically(
                    html=html,
                    query=action.query,
                    max_results=action.max_results or 20,
                    similarity_threshold=action.similarity_threshold or 0.3,
                )
                return {"status": "success", "content": [{"text": filtered_result}]}

            # No query - return truncated raw HTML
            truncated = html[:2000] + "..." if len(html) > 2000 else html
            logger.info(f"Returning raw HTML (truncated to {len(truncated)} chars)")
            return {"status": "success", "content": [{"text": truncated}]}

        except Exception as e:
            logger.error(f"Get HTML failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Get HTML failed: {str(e)}"}]}

    def screenshot(self, action: ScreenshotAction) -> Dict[str, Any]:
        """Take a screenshot."""
        return self._execute_async(self._async_screenshot(action))

    async def _async_screenshot(self, action: ScreenshotAction) -> Dict[str, Any]:
        """Async screenshot implementation - returns image for LLM to see."""
        logger.debug(f"Screenshot action: session={action.session_name}, path={action.path}")

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Screenshot validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Screenshot failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            screenshots_dir = os.getenv("STRANDS_BROWSER_SCREENSHOTS_DIR", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            if not action.path:
                filename = f"screenshot_{int(time.time())}.png"
                path = os.path.join(screenshots_dir, filename)
            else:
                path = action.path

            logger.debug(f"Taking screenshot to: {path}")
            # Take screenshot and save to disk
            await page.screenshot(path=path)

            # Read screenshot at full resolution (no downscaling)
            # This ensures coordinates in screenshots match click coordinates exactly
            with open(path, "rb") as f:
                image_bytes = f.read()

            logger.debug(f"Screenshot successful: {path}, size: {len(image_bytes)} bytes")
            return {
                "status": "success",
                "content": [
                    {"text": f"Screenshot saved: {path}"},
                    {"image": {"format": "png", "source": {"bytes": image_bytes}}},
                ],
            }
        except Exception as e:
            logger.error(f"Screenshot failed: {e}", exc_info=True)
            return {"status": "error", "content": [{"text": f"Screenshot failed: {str(e)}"}]}

    # Enhanced Actions
    def _execute_action_list(self, actions: list) -> Dict[str, Any]:
        """Execute a list of actions in sequence (new direct list support)."""
        return self._execute_async(self._async_execute_action_list(actions))

    async def _async_execute_action_list(self, actions: list) -> Dict[str, Any]:
        """Async execution of action list."""
        logger.debug(f"Executing action list with {len(actions)} actions")

        # Get session_name from first action for validation
        if not actions:
            return {"status": "error", "content": [{"text": "Empty action list"}]}

        first_session = getattr(actions[0], 'session_name', None)
        if first_session:
            error_response = self.validate_session(first_session)
            if error_response:
                logger.error(f"Action list validation failed: session '{first_session}' not found")
                return error_response

        results = []
        for i, sub_action in enumerate(actions):
            logger.info(f"Action {i+1}/{len(actions)}: {type(sub_action).__name__}")
            logger.debug(f"Action details: type={sub_action.type}, session_name={getattr(sub_action, 'session_name', 'MISSING')}")

            # Log specific action parameters
            if isinstance(sub_action, NavigateAction):
                logger.debug(f"  -> Navigate to: {sub_action.url}")
            elif isinstance(sub_action, ClickAction):
                if sub_action.x is not None and sub_action.y is not None:
                    logger.debug(f"  -> Click coordinates: ({sub_action.x}, {sub_action.y})")
                else:
                    logger.debug(f"  -> Click selector: {sub_action.selector}")
            elif isinstance(sub_action, TypeAction):
                logger.debug(f"  -> Type into: {sub_action.selector}, text length: {len(sub_action.text)}")

            # Execute sub-action by calling appropriate async method
            try:
                if isinstance(sub_action, InitSessionAction):
                    result = await self._async_init_session(sub_action)
                elif isinstance(sub_action, NavigateAction):
                    result = await self._async_navigate(sub_action)
                elif isinstance(sub_action, ClickAction):
                    result = await self._async_click(sub_action)
                elif isinstance(sub_action, TypeAction):
                    result = await self._async_type_text(sub_action)
                elif isinstance(sub_action, KeyPressAction):
                    result = await self._async_key_press(sub_action)
                elif isinstance(sub_action, GetTextAction):
                    result = await self._async_get_text(sub_action)
                elif isinstance(sub_action, GetHtmlAction):
                    result = await self._async_get_html(sub_action)
                elif isinstance(sub_action, ScreenshotAction):
                    result = await self._async_screenshot(sub_action)
                elif isinstance(sub_action, WaitAction):
                    result = await self._async_wait(sub_action)
                elif isinstance(sub_action, ScrollAction):
                    result = await self._async_scroll(sub_action)
                elif isinstance(sub_action, HoverAction):
                    result = await self._async_hover(sub_action)
                elif isinstance(sub_action, ScrollToTopAction):
                    result = await self._async_scroll_to_top(sub_action)
                elif isinstance(sub_action, ScrollToBottomAction):
                    result = await self._async_scroll_to_bottom(sub_action)
                elif isinstance(sub_action, EvaluateJsAction):
                    result = await self._async_evaluate_js(sub_action)
                elif isinstance(sub_action, GetAccessibilityTreeAction):
                    result = await self._async_get_accessibility_tree(sub_action)
                elif isinstance(sub_action, CloseAction):
                    result = await self._async_close(sub_action)
                else:
                    logger.error(f"Unknown action type: {type(sub_action)}")
                    result = {"status": "error", "content": [{"text": f"Unknown action: {type(sub_action)}"}]}

                logger.debug(f"Action {i+1} completed with status: {result.get('status')}")
                if result.get("status") == "error":
                    logger.error(f"Action {i+1} error content: {result.get('content')}")

                results.append(result)

                # Stop on error
                if result.get("status") == "error":
                    logger.warning(f"Action {i+1} failed, stopping execution")
                    break

            except Exception as e:
                logger.error(f"Exception in action {i+1}: {e}", exc_info=True)
                error_result = {"status": "error", "content": [{"text": f"Action {i+1} failed: {str(e)}"}]}
                results.append(error_result)
                break

        # Consolidate results
        success_count = sum(1 for r in results if r.get("status") == "success")
        total_count = len(results)

        content_items = [{"text": f"Executed {success_count}/{total_count} actions successfully"}]

        # Flatten each action's content into the response
        for result in results:
            if result.get("content"):
                content_items.extend(result["content"])

        return {
            "status": "success" if success_count == total_count else "error",
            "content": content_items,
        }

    def get_accessibility_tree(self, action: GetAccessibilityTreeAction) -> Dict[str, Any]:
        """Get the accessibility tree."""
        return self._execute_async(self._async_get_accessibility_tree(action))

    async def _async_get_accessibility_tree(
        self, action: GetAccessibilityTreeAction
    ) -> Dict[str, Any]:
        """Async get accessibility tree implementation."""
        logger.debug(
            f"Get accessibility tree: session={action.session_name}, "
            f"query={action.query}, max_depth={action.max_depth}, "
            f"max_results={action.max_results}, threshold={action.similarity_threshold}, "
            f"strategy={action.chunking_strategy}"
        )

        error_response = self.validate_session(action.session_name)
        if error_response:
            logger.error(f"Accessibility tree validation failed: {error_response}")
            return error_response

        page = self.get_session_page(action.session_name)
        if not page:
            logger.error("Accessibility tree failed: No active page")
            return {"status": "error", "content": [{"text": "No active page"}]}

        try:
            # Convert string to enum for chunking strategy
            strategy = ChunkingStrategy(action.chunking_strategy or "subtrees")

            logger.debug("Extracting accessibility tree...")
            tree_text = await self._accessibility_extractor.get_filtered_accessibility_tree(
                page,
                query=action.query,
                max_depth=action.max_depth or 5,
                max_results=action.max_results or 20,
                similarity_threshold=action.similarity_threshold or 0.3,
                chunking_strategy=strategy,
                filter_states=action.filter_states,
                filter_roles=action.filter_roles,
            )

            logger.debug(f"Accessibility tree extracted successfully, length: {len(tree_text) if tree_text else 0} chars")
            return {"status": "success", "content": [{"text": tree_text}]}
        except Exception as e:
            logger.error(f"Failed to get accessibility tree: {e}", exc_info=True)
            return {
                "status": "error",
                "content": [{"text": f"Accessibility tree failed: {str(e)}"}],
            }

    def close(self, action: CloseAction) -> Dict[str, Any]:
        """Close a session."""
        return self._execute_async(self._async_close(action))

    async def _async_close(self, action: CloseAction) -> Dict[str, Any]:
        """Async close implementation."""
        session = self._sessions.get(action.session_name)
        if not session:
            return {
                "status": "error",
                "content": [{"text": f"Session '{action.session_name}' not found"}],
            }

        try:
            await session.close()
            del self._sessions[action.session_name]
            return {"status": "success", "content": [{"text": "Session closed"}]}
        except Exception as e:
            return {"status": "error", "content": [{"text": f"Close failed: {str(e)}"}]}

    def __del__(self):
        """Cleanup on destruction."""
        try:
            for session in list(self._sessions.values()):
                self._execute_async(session.close())
            self.close_platform()
            if self._playwright:
                self._execute_async(self._playwright.stop())
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")
