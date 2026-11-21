"""Схема отчёта и её валидация."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

NOT_SPECIFIED = "не указано"
TEXT_LIMIT = 300
ITEM_LIMIT = 120
LIST_LIMIT = 6

EMPTY_MARKERS = {NOT_SPECIFIED, "нет", "неизвестно", "null", "none", "-", "не указан"}


def clean_text(value: Any, default: str = NOT_SPECIFIED) -> str:
    if value is None:
        return default
    text = str(value).strip().strip(".,;:")
    if not text or text.lower() in EMPTY_MARKERS:
        return default
    return text[:TEXT_LIMIT]


def clean_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if number > 0 else None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    number = int(digits)
    return number if number > 0 else None


def clean_money(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 0 else None
    text = re.sub(r"[^\d,.]", "", str(value)).replace(",", ".")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number > 0 else None


def clean_list(value: Any, limit: int = LIST_LIMIT) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in items:
        text = str(item).strip().strip(".,;:")
        if not text or text.lower() in EMPTY_MARKERS:
            continue
        result.append(text[:ITEM_LIMIT])
        if len(result) >= limit:
            break
    return result


class ReportData(BaseModel):
    """Данные отчёта. Одна модель для обоих типов отчёта."""

    model_config = ConfigDict(extra="ignore")

    client_name: str = NOT_SPECIFIED
    contact: str = NOT_SPECIFIED
    country: str = NOT_SPECIFIED
    city: str = NOT_SPECIFIED
    dates: str = NOT_SPECIFIED
    nights: int | None = Field(default=None, ge=1, le=60)
    people: int | None = Field(default=None, ge=1, le=20)
    budget: float | None = Field(default=None, gt=0)
    preferences: list[str] = Field(default_factory=list, max_length=6)
    topic: str = NOT_SPECIFIED
    main_request: str = NOT_SPECIFIED
    mood: str = NOT_SPECIFIED
    risks: list[str] = Field(default_factory=list, max_length=5)
    next_steps: list[str] = Field(default_factory=list, max_length=6)
    manager: str = NOT_SPECIFIED
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("client_name", "contact", "country", "city", "dates", "topic",
                     "main_request", "mood", "manager", mode="before")
    @classmethod
    def _text_fields(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("nights", "people", mode="before")
    @classmethod
    def _ints(cls, value: Any) -> int | None:
        return clean_int(value)

    @field_validator("budget", mode="before")
    @classmethod
    def _budget(cls, value: Any) -> float | None:
        return clean_money(value)

    @field_validator("preferences", "risks", "next_steps", mode="before")
    @classmethod
    def _lists(cls, value: Any) -> list[str]:
        return clean_list(value)

    # ------------------------------------------------------------ удобства

    def missing_fields(self) -> list[str]:
        """Каких данных не хватает — считается кодом, а не моделью."""
        labels = {
            "client_name": "имя клиента",
            "contact": "контакт клиента",
            "country": "страна",
            "city": "город",
            "dates": "даты поездки",
            "nights": "число ночей",
            "people": "число человек",
            "budget": "бюджет",
        }
        missing = []
        for field, label in labels.items():
            value = getattr(self, field)
            if value is None or value == NOT_SPECIFIED:
                missing.append(label)
        return missing

    def budget_text(self) -> str:
        if self.budget is None:
            return NOT_SPECIFIED
        return f"{self.budget:,.0f}".replace(",", " ") + " ₽"

    def trip_text(self) -> str:
        parts = []
        if self.nights is not None:
            parts.append(f"{self.nights} ночей")
        if self.people is not None:
            parts.append(f"{self.people} чел.")
        return ", ".join(parts) if parts else NOT_SPECIFIED