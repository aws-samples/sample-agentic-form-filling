"""Configuration management for the airline check-in agent."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfig:
    """Configuration for the AI model."""

    model_id: str = "global.anthropic.claude-opus-4-5-20251101-v1:0"
    region: str = "eu-west-1"
    temperature: float = 0.2
    max_tokens: int = 2048


@dataclass
class BrowserConfig:
    """Configuration for the browser."""

    headless: bool = True
    width: int = 1024  # Reduced from 1280 (20% smaller, still desktop layout)
    height: int = 720  # Reduced from 800 (4% smaller, maintains aspect ratio)
    screenshots_dir: str = "screenshots"


@dataclass
class CheckInConfig:
    """Configuration for check-in credentials and preferences."""

    airline_url: str = "http://localhost:8001/"
    login: str = "Stiles"
    code: str = "QF456"
    seat_preference: str = "between row 10 and row 14, seat placed on aisle or window if not available"


@dataclass
class MemoryConfig:
    """Configuration for AgentCore episodic memory."""

    enabled: bool = True  # Enable/disable AgentCore memory
    memory_id: Optional[str] = None  # Memory store ID (auto-created if not set)


@dataclass
class Config:
    """Main configuration container."""

    model: ModelConfig
    browser: BrowserConfig
    checkin: CheckInConfig
    memory: MemoryConfig

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables with fallbacks."""
        # Detect container environment
        is_container = os.path.exists("/.dockerenv") or os.getenv("CONTAINER") == "true"

        model_config = ModelConfig(
            model_id=os.getenv(
                #"MODEL_ID", "global.amazon.nova-2-lite-v1:0"#"global.anthropic.claude-haiku-4-5-20251001-v1:0"
                #"MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
                #"MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
                "MODEL_ID", "global.anthropic.claude-opus-4-5-20251101-v1:0"
                #"MODEL_ID","openai.gpt-oss-120b-1:0"
            ),
            region=os.getenv("AWS_REGION", "us-west-2"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("MODEL_MAX_TOKENS", "3096")),
        )

        browser_config = BrowserConfig(
            headless=is_container or os.getenv("STRANDS_BROWSER_HEADLESS", "true").lower() == "true",
            width=int(os.getenv("STRANDS_BROWSER_WIDTH", "1024")),
            height=int(os.getenv("STRANDS_BROWSER_HEIGHT", "720")),
            screenshots_dir=os.getenv("STRANDS_BROWSER_SCREENSHOTS_DIR", "screenshots"),
        )

        checkin_config = CheckInConfig(
            airline_url=os.getenv(
                "AIRLINE_URL", "http://localhost:8001/"
            ),
            login=os.getenv("CHECK_IN_LOGIN", "Stiles"),
            code=os.getenv("CHECK_IN_CODE", "QF456"),
            seat_preference=os.getenv(
                "SEAT_PREFERENCE",
                "between row 10 and row 14, seat placed on aisle or window if not available",
            ),
        )

        memory_config = MemoryConfig(
            enabled=os.getenv("AGENTCORE_MEMORY_ENABLED", "true").lower() == "true",
            memory_id=os.getenv("AGENTCORE_MEMORY_ID"),
        )

        return cls(
            model=model_config,
            browser=browser_config,
            checkin=checkin_config,
            memory=memory_config,
        )


# Global configuration instance
config = Config.from_env()
