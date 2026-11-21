"""Настройки из .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    chat_model: str
    chat_temperature: float
    max_input_chars: int
    reports_dir: Path
    templates_dir: Path
    log_level: str
    request_timeout: float
    retries: int

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("В .env не задан PROXYAPI_KEY")


settings = Settings(
    api_key=os.getenv("PROXYAPI_KEY", "").strip(),
    base_url=os.getenv("LLM_BASE_URL", "https://api.proxyapi.ru/openai/v1").rstrip("/"),
    chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini").strip(),
    chat_temperature=_get_float("CHAT_TEMPERATURE", 0.2),
    max_input_chars=_get_int("MAX_INPUT_CHARS", 20000),
    reports_dir=BASE / os.getenv("REPORTS_DIR", "./reports"),
    templates_dir=BASE / os.getenv("TEMPLATES_DIR", "./templates"),
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    request_timeout=_get_float("REQUEST_TIMEOUT", 90.0),
    retries=_get_int("RETRIES", 1),
)