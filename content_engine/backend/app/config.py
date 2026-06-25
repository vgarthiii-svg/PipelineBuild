"""Central configuration loaded from environment variables.

All runtime behavior (which AI/research provider, DB target, auth mode) is
controlled here so the app stays portable across local, container, and cloud.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings sourced from the environment with safe defaults."""

    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret")

        # AI provider
        self.ai_provider: str = os.getenv("AI_PROVIDER", "anthropic").lower()
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

        # Research provider
        self.research_provider: str = os.getenv("RESEARCH_PROVIDER", "anthropic_web").lower()

        # Database
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/content_engine.db")

        # Auth
        self.single_user_mode: bool = os.getenv("SINGLE_USER_MODE", "1") == "1"
        self.default_user_email: str = os.getenv("DEFAULT_USER_EMAIL", "owner@local")

    @property
    def ai_enabled(self) -> bool:
        """True when a real Anthropic key is configured."""
        return self.ai_provider == "anthropic" and bool(self.anthropic_api_key)

    @property
    def research_enabled(self) -> bool:
        return self.research_provider == "anthropic_web" and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
