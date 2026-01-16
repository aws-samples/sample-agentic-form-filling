"""
Extended Pydantic models for Enhanced Browser tool.

This module defines action types for browser operations and accessibility tree extraction.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# Import base models from reference implementation
# We'll redefine the essentials here for standalone operation


class InitSessionAction(BaseModel):
    """Initialize a new browser session."""

    type: Literal["init_session"] = Field(description="Initialize a new browser session")
    description: str = Field(description="Description of what this session will be used for")
    session_name: str = Field(
        pattern="^[a-z0-9-]+$",
        min_length=10,
        max_length=36,
        description="Name to identify the session",
    )
    url: Optional[str] = Field(
        default=None,
        description="Optional initial URL for the session. If provided and it's a CloudFront URL, signed cookies will be automatically configured.",
    )


class NavigateAction(BaseModel):
    """Navigate to a URL."""

    type: Literal["navigate"] = Field(description="Navigate to a URL")
    session_name: str = Field(description="Session name from init_session")
    url: str = Field(description="URL to navigate to")


class ClickAction(BaseModel):
    """
    Click on an element by CSS selector OR coordinates.

    Use coordinates (x, y) when you can see the element in a screenshot but don't know the selector.
    Use selector when you know the exact CSS selector.

    Examples:
    - Click by coordinates: {"type": "click", "session_name": "...", "x": 640, "y": 400}
    - Click by selector: {"type": "click", "session_name": "...", "selector": "button#submit"}
    """

    type: Literal["click"] = Field(description="Click on an element")
    session_name: str = Field(description="Session name from init_session")
    selector: Optional[str] = Field(default=None, description="CSS selector for the element")
    x: Optional[int] = Field(default=None, description="X coordinate for click (pixels from left)")
    y: Optional[int] = Field(default=None, description="Y coordinate for click (pixels from top)")


class TypeAction(BaseModel):
    """Type text into an element."""

    type: Literal["type"] = Field(description="Type text into an element")
    session_name: str = Field(description="Session name from init_session")
    selector: str = Field(description="CSS selector for the element")
    text: str = Field(description="Text to type")


class KeyPressAction(BaseModel):
    """
    Press a keyboard key or key combination.

    Supports special keys like Enter, Backspace, Tab, Escape, arrow keys, etc.
    Can also press key combinations like Control+A, Shift+End.

    Examples:
    - Press Enter: {"type": "key_press", "session_name": "...", "key": "Enter"}
    - Press Backspace: {"type": "key_press", "session_name": "...", "key": "Backspace"}
    - Press Tab: {"type": "key_press", "session_name": "...", "key": "Tab"}
    - Press Ctrl+A: {"type": "key_press", "session_name": "...", "key": "Control+A"}
    - Press arrow down: {"type": "key_press", "session_name": "...", "key": "ArrowDown"}

    Common keys: Enter, Escape, Backspace, Delete, Tab, Space, ArrowLeft, ArrowRight,
                 ArrowUp, ArrowDown, Home, End, PageUp, PageDown
    """

    type: Literal["key_press"] = Field(description="Press a keyboard key")
    session_name: str = Field(description="Session name from init_session")
    key: str = Field(description="Key to press (e.g., 'Enter', 'Backspace', 'Control+A')")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to focus before pressing key")


class GetTextAction(BaseModel):
    """Get text content from an element."""

    type: Literal["get_text"] = Field(description="Get text content")
    session_name: str = Field(description="Session name from init_session")
    selector: str = Field(description="CSS selector for the element")


class GetHtmlAction(BaseModel):
    """
    Get HTML content from the page, optionally filtered by semantic relevance.

    WITHOUT QUERY: Returns raw HTML (truncated to 2000 chars by default)
    WITH QUERY: Parses HTML into elements and returns semantically relevant ones

    SEMANTIC FILTERING: When a query is provided, the HTML is parsed into elements
    and filtered using local embedding models (sentence-transformers) to find
    elements matching your intent.

    Examples:
    - Get full page HTML: {"type": "get_html", "session_name": "..."}
    - Get HTML of specific element: {"type": "get_html", "session_name": "...", "selector": "div.content"}
    - Find login-related elements: {"type": "get_html", "session_name": "...", "query": "login form"}
    - Find navigation elements: {"type": "get_html", "session_name": "...", "query": "navigation menu links"}

    Example output (with query="submit button"):
    Filtered HTML Elements (3 matches for: 'submit button')

    1. [92%] <button type="submit" class="btn-primary">Submit</button>
    2. [78%] <button class="continue-btn">Continue</button>
    3. [65%] <input type="submit" value="Send">
    """

    type: Literal["get_html"] = Field(description="Get HTML content")
    session_name: str = Field(description="Session name from init_session")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to scope the HTML extraction")
    query: Optional[str] = Field(
        default=None,
        description="Semantic search query to filter HTML elements (e.g., 'submit button', 'login form', 'navigation links')",
    )
    max_results: Optional[int] = Field(
        default=20, description="Maximum number of elements to return when filtering"
    )
    similarity_threshold: Optional[float] = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1) for semantic filtering. Lower values return more results.",
    )


class ScreenshotAction(BaseModel):
    """Take a screenshot."""

    type: Literal["screenshot"] = Field(description="Take a screenshot")
    session_name: str = Field(description="Session name from init_session")
    path: Optional[str] = Field(default=None, description="Optional path for screenshot")


class CloseAction(BaseModel):
    """Close the browser."""

    type: Literal["close"] = Field(description="Close the browser")
    session_name: str = Field(description="Session name from init_session")


class WaitAction(BaseModel):
    """Wait for a specified time or condition."""

    type: Literal["wait"] = Field(description="Wait for time or condition")
    session_name: str = Field(description="Session name from init_session")
    selector: Optional[str] = Field(default=None, description="Wait for element selector")
    timeout: Optional[int] = Field(default=5000, description="Timeout in milliseconds")


class ScrollAction(BaseModel):
    """
    Scroll the page by a specified amount or to a specific position.

    Examples:
    - Scroll down 500 pixels: {"type": "scroll", "session_name": "...", "y": 500}
    - Scroll up 300 pixels: {"type": "scroll", "session_name": "...", "y": -300}
    - Scroll right 200 pixels: {"type": "scroll", "session_name": "...", "x": 200}
    """

    type: Literal["scroll"] = Field(description="Scroll the page")
    session_name: str = Field(description="Session name from init_session")
    x: Optional[int] = Field(default=0, description="Horizontal scroll amount in pixels (positive = right, negative = left)")
    y: Optional[int] = Field(default=0, description="Vertical scroll amount in pixels (positive = down, negative = up)")


class HoverAction(BaseModel):
    """
    Hover over an element at specific coordinates.

    Useful to verify element position before clicking or to trigger hover states.

    Examples:
    - Hover at coordinates: {"type": "hover", "session_name": "...", "x": 640, "y": 400}
    """

    type: Literal["hover"] = Field(description="Hover over an element")
    session_name: str = Field(description="Session name from init_session")
    x: int = Field(description="X coordinate for hover (pixels from left)")
    y: int = Field(description="Y coordinate for hover (pixels from top)")


class ScrollToTopAction(BaseModel):
    """
    Scroll to the very top of the page (y=0).

    Example:
    - Scroll to top: {"type": "scroll_to_top", "session_name": "..."}
    """

    type: Literal["scroll_to_top"] = Field(description="Scroll to the top of the page")
    session_name: str = Field(description="Session name from init_session")


class ScrollToBottomAction(BaseModel):
    """
    Scroll to the very bottom of the page.

    Example:
    - Scroll to bottom: {"type": "scroll_to_bottom", "session_name": "..."}
    """

    type: Literal["scroll_to_bottom"] = Field(description="Scroll to the bottom of the page")
    session_name: str = Field(description="Session name from init_session")


class EvaluateJsAction(BaseModel):
    """
    Execute JavaScript code in the browser and return the result.

    USE THIS WHEN:
    - You need to extract data from the page that's not in the accessibility tree
    - You need to interact with elements in complex ways
    - You need to get computed styles, positions, or other DOM properties
    - You need to trigger events or call page functions

    Examples:
    - Get page title: {"type": "evaluate_js", "session_name": "...", "script": "document.title"}
    - Get element text: {"type": "evaluate_js", "session_name": "...", "script": "document.querySelector('h1').textContent"}
    - Get all links: {"type": "evaluate_js", "session_name": "...", "script": "Array.from(document.querySelectorAll('a')).map(a => ({href: a.href, text: a.textContent}))"}
    - Click by text: {"type": "evaluate_js", "session_name": "...", "script": "document.querySelector('button:contains(Submit)').click()"}
    """

    type: Literal["evaluate_js"] = Field(description="Execute JavaScript in the browser")
    session_name: str = Field(description="Session name from init_session")
    script: str = Field(description="JavaScript code to execute. The result will be returned as JSON.")


class GetAccessibilityTreeAction(BaseModel):
    """
    DISCOVER CLICKABLE ELEMENTS: Get a list of all interactive elements on the page.

    USE THIS WHEN:
    - You can't find a button, link, or input field visually in the screenshot
    - You need to know what elements can be clicked or typed into
    - You want to understand what actions are available on the page
    - A click missed its target and you need to find the correct element

    RETURNS: A structured list of ALL interactive elements (buttons, links, inputs,
    checkboxes, etc.) with their roles and labels - perfect for finding click targets.

    SEMANTIC FILTERING: When a query is provided, results are filtered using local
    embedding models (sentence-transformers) to find semantically relevant elements.

    Example output (without query):
    - button "Continue" [focused]
    - textbox "Confirmation Code"
    - link "Skip to seat selection"
    - checkbox "Add travel insurance"

    Example output (with query="submit"):
    Filtered Accessibility Tree (3 matches for: 'submit')
    1. [92%] button "Submit"
    2. [78%] button "Continue"
    3. [65%] link "Submit feedback"
    """

    type: Literal["get_accessibility_tree"] = Field(description="DISCOVER all clickable/interactive elements on page")
    session_name: str = Field(description="Session name from init_session")
    query: Optional[str] = Field(
        default=None,
        description="Semantic search query to filter elements (e.g., 'submit button', 'login form', 'navigation links')",
    )
    max_depth: Optional[int] = Field(
        default=5, description="Maximum depth to traverse in the tree"
    )
    max_results: Optional[int] = Field(
        default=20, description="Maximum number of elements to return when filtering"
    )
    similarity_threshold: Optional[float] = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1) for semantic filtering. Lower values return more results.",
    )
    chunking_strategy: Optional[str] = Field(
        default="subtrees",
        description="How to chunk the tree: 'individual_nodes' (each element separately) or 'subtrees' (element with descendants)",
    )
    filter_states: Optional[List[str]] = Field(
        default=None,
        description=(
            "Filter nodes by ARIA state attributes. Use '+state' to include only nodes WITH that state, "
            "'-state' to EXCLUDE nodes with that state. "
            "Examples: ['-disabled'] returns only enabled elements, ['+checked'] returns only checked elements, "
            "['-disabled', '+focused'] returns enabled AND focused elements. "
            "Available states: checked, disabled, expanded, selected, pressed, focused, required, level"
        ),
    )
    filter_roles: Optional[List[str]] = Field(
        default=None,
        description=(
            "Filter nodes by ARIA role. Only include nodes matching these roles. "
            "Examples: ['button'] returns only buttons, ['button', 'link'] returns buttons and links. "
            "Common roles: button, link, textbox, checkbox, radio, combobox, menuitem, listitem, heading"
        ),
    )


# Define single action type for reuse
SingleAction = Union[
    InitSessionAction,
    NavigateAction,
    ClickAction,
    TypeAction,
    KeyPressAction,
    GetTextAction,
    GetHtmlAction,
    ScreenshotAction,
    CloseAction,
    WaitAction,
    ScrollAction,
    HoverAction,
    ScrollToTopAction,
    ScrollToBottomAction,
    EvaluateJsAction,
    GetAccessibilityTreeAction,
]


class EnhancedBrowserInput(BaseModel):
    """
    Input model for enhanced browser actions.

    Accepts either a single action OR a list of actions to execute in sequence.

    SINGLE ACTION EXAMPLE:
    {"action": {"type": "click", "session_name": "my-session", "x": 640, "y": 400}}

    LIST OF ACTIONS EXAMPLE (preferred for efficiency):
    {"action": [
        {"type": "click", "session_name": "my-session", "x": 640, "y": 400},
        {"type": "screenshot", "session_name": "my-session"}
    ]}

    When a list is provided, actions execute in sequence and stop on first error.
    All action results are consolidated into a single response.
    """

    action: Union[
        SingleAction,
        List[SingleAction],
    ] = Field(description="Single action or list of actions to execute")
    wait_time: Optional[int] = Field(
        default=0, description="Time to wait after action in seconds (0 for maximum speed)"
    )
