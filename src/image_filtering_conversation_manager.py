"""Custom conversation manager with aggressive image filtering.

This module provides a conversation manager that extends SlidingWindowConversationManager
to filter out old images before each model call, significantly reducing context size
for browser automation tasks where each tool call returns a screenshot.
"""

import copy
import logging
from typing import TYPE_CHECKING, Any

from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeModelCallEvent

if TYPE_CHECKING:
    from strands.types.content import Messages

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARN)


class ImageFilteringConversationManager(SlidingWindowConversationManager, HookProvider):
    """Conversation manager that filters images before each model call.

    This manager extends SlidingWindowConversationManager to:
    1. Preserve the first user message (initial task/intent)
    2. Keep a sliding window of remaining messages
    3. Filter images to keep only the last N images
    4. Apply filtering before EACH model call via BeforeModelCallEvent hook

    The key difference from the base class is that:
    - The first user message is always preserved (task intent)
    - Image filtering happens before every model inference, not just at end of turn

    This is critical for browser automation where each tool call returns a screenshot
    and the agent needs to remember the original task.

    Example:
        conversation_manager = ImageFilteringConversationManager(
            window_size=5,
            should_truncate_results=True,
            max_images=2  # Keep only last 2 screenshots
        )

        agent = Agent(
            model=model,
            tools=[...],
            conversation_manager=conversation_manager,
            hooks=[conversation_manager]  # Register as hook provider
        )
    """

    def __init__(
        self,
        window_size: int = 40,
        should_truncate_results: bool = True,
        max_images: int = 2
    ):
        """Initialize the image filtering conversation manager.

        Args:
            window_size: Maximum number of messages to keep in history.
                Defaults to 40 messages.
            should_truncate_results: Whether to truncate tool results when
                context window overflows. Defaults to True.
            max_images: Maximum number of images to keep in context.
                Only the most recent N images are retained.
                Defaults to 2 images.
        """
        super().__init__(window_size, should_truncate_results)
        self.max_images = max_images
        self._images_removed_count = 0
        self._first_user_message: dict | None = None

    def apply_management(self, agent: "Any", **kwargs: Any) -> None:
        """Apply sliding window management while preserving the first user message.

        This overrides the parent's apply_management to:
        1. Save the first user message (the initial task/intent)
        2. Apply the sliding window to remaining messages
        3. Ensure the first message is always at the start

        Args:
            agent: The agent whose conversation history will be managed.
            **kwargs: Additional keyword arguments for future extensibility.
        """
        messages = agent.messages

        # Nothing to manage if empty
        if not messages:
            return

        # Capture and preserve the first user message (initial task intent)
        if self._first_user_message is None and messages:
            first_msg = messages[0]
            if first_msg.get("role") == "user":
                # Deep copy to avoid mutation
                self._first_user_message = copy.deepcopy(first_msg)
                logger.debug("Preserved first user message as task intent")

        # If we have a preserved first message and it's been removed, restore it
        if self._first_user_message is not None:
            # Check if first message is still the original
            if not messages or messages[0] != self._first_user_message:
                # Check if content matches (messages might be different objects)
                first_matches = (
                    messages and
                    messages[0].get("role") == "user" and
                    messages[0].get("content") == self._first_user_message.get("content")
                )
                if not first_matches:
                    # Apply parent's sliding window first
                    super().apply_management(agent, **kwargs)

                    # Then ensure first message is preserved at start
                    if messages and messages[0] != self._first_user_message:
                        # Insert the preserved first message at the beginning
                        messages.insert(0, self._first_user_message)
                        logger.debug("Restored first user message after sliding window")
                    return

        # Normal case: apply parent's sliding window
        super().apply_management(agent, **kwargs)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register BeforeModelCallEvent to filter images before each model call.

        This is called by the Agent when the conversation manager is passed
        as a hook provider.

        Args:
            registry: The hook registry to register callbacks with.
            **kwargs: Additional keyword arguments for future extensibility.
        """
        registry.add_callback(BeforeModelCallEvent, self._on_before_model_call)
        logger.debug("Registered BeforeModelCallEvent callback for image filtering")

    def _on_before_model_call(self, event: BeforeModelCallEvent) -> None:
        """Apply conversation management and filter images before each model call.

        This callback is invoked before every model inference, allowing us
        to reduce context size before the model sees the messages by:
        1. Applying sliding window management (trim old messages)
        2. Filtering images to keep only the last N

        Args:
            event: The BeforeModelCallEvent containing the agent reference.
        """
        logger.debug("BeforeModelCallEvent: applying management before model call")

        # First, apply sliding window management to trim old messages
        self.apply_management(event.agent)

        # Then filter images
        removed = self._filter_images(event.agent.messages)
        if removed > 0:
            self._images_removed_count += removed
            logger.info(
                "IMAGE_FILTER: removed %d images before model call (total removed: %d)",
                removed,
                self._images_removed_count
            )

    def _filter_images(self, messages: "Messages") -> int:
        """Remove all image content blocks except the last max_images.

        This method modifies messages in-place, replacing old image blocks
        with placeholder text to maintain message structure integrity.

        Images can be found in two locations:
        1. Top-level: message["content"][idx]["image"]
        2. Inside tool results: message["content"][idx]["toolResult"]["content"][idx2]["image"]

        Args:
            messages: The conversation message history to filter.

        Returns:
            Number of images removed.
        """
        logger.debug(
            "filter_images: scanning %d messages, max_images=%d",
            len(messages), self.max_images
        )

        # 1. Collect all image locations
        # Each location is (msg_idx, content_idx, tool_result_content_idx or None)
        # If tool_result_content_idx is None, it's a top-level image
        image_locations: list[tuple[int, int, int | None]] = []
        for msg_idx, message in enumerate(messages):
            for content_idx, content in enumerate(message.get("content", [])):
                if isinstance(content, dict):
                    # Check for top-level image
                    if "image" in content:
                        image_locations.append((msg_idx, content_idx, None))
                        logger.debug(
                            "filter_images: found top-level image at msg[%d].content[%d]",
                            msg_idx, content_idx
                        )
                    # Check for images inside toolResult
                    if "toolResult" in content:
                        tool_result = content["toolResult"]
                        if isinstance(tool_result, dict) and "content" in tool_result:
                            for tr_content_idx, tr_content in enumerate(tool_result["content"]):
                                if isinstance(tr_content, dict) and "image" in tr_content:
                                    image_locations.append((msg_idx, content_idx, tr_content_idx))
                                    logger.debug(
                                        "filter_images: found toolResult image at msg[%d].content[%d].toolResult.content[%d]",
                                        msg_idx, content_idx, tr_content_idx
                                    )

        logger.debug(
            "filter_images: found %d total images in conversation",
            len(image_locations)
        )

        # 2. If more than max_images, remove the oldest ones
        if len(image_locations) <= self.max_images:
            logger.debug(
                "filter_images: %d images <= max_images=%d, no removal needed",
                len(image_locations), self.max_images
            )
            return 0

        # Keep the last max_images, remove the rest
        to_remove = image_locations[:-self.max_images] if self.max_images > 0 else image_locations
        to_keep = image_locations[-self.max_images:] if self.max_images > 0 else []

        logger.debug(
            "filter_images: removing %d images, keeping %d (at positions: %s)",
            len(to_remove), len(to_keep), to_keep
        )

        # Remove by replacing with placeholder text (maintains message structure)
        for msg_idx, content_idx, tr_content_idx in to_remove:
            if tr_content_idx is None:
                # Top-level image
                logger.debug(
                    "filter_images: replacing top-level image at msg[%d].content[%d] with placeholder",
                    msg_idx, content_idx
                )
                messages[msg_idx]["content"][content_idx] = {
                    "text": "[Screenshot removed to reduce context]"
                }
            else:
                # Image inside toolResult
                logger.debug(
                    "filter_images: replacing toolResult image at msg[%d].content[%d].toolResult.content[%d] with placeholder",
                    msg_idx, content_idx, tr_content_idx
                )
                messages[msg_idx]["content"][content_idx]["toolResult"]["content"][tr_content_idx] = {
                    "text": "[Screenshot removed to reduce context]"
                }

        logger.info(
            "IMAGE_FILTER: removed %d images, kept last %d (total removed so far: %d)",
            len(to_remove), len(to_keep), self._images_removed_count + len(to_remove)
        )

        return len(to_remove)

    def get_state(self) -> dict[str, Any]:
        """Get the current state including image removal stats.

        Returns:
            Dictionary with conversation manager state.
        """
        state = super().get_state()
        state["images_removed_count"] = self._images_removed_count
        return state
