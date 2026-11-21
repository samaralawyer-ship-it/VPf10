"""Запрос к модели, разбор JSON и валидация с одним повтором."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.models import ReportData
from app.prompts import build_messages, repair_messages

logger = logging.getLogger(__name__)


class AIProcessorError(RuntimeError):
    """Модель не дала корректных данных."""


def extract_json_object(raw: str) -> dict:
    """Достать первый законченный JSON-объект из ответа модели."""
    if not raw or not raw.strip():
        raise AIProcessorError("модель вернула пустой ответ")

    text = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
    start = text.find("{")
    if start < 0:
        raise AIProcessorError("в ответе модели нет JSON-объекта")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1]
                try:
                    data = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise AIProcessorError(f"JSON не разобрался: {exc.msg}") from exc
                if not isinstance(data, dict):
                    raise AIProcessorError("ожидался JSON-объект, а пришёл другой тип")
                return data

    raise AIProcessorError("JSON-объект не закрыт")


def _describe_error(error: Exception) -> str:
    if isinstance(error, ValidationError):
        problems = []
        for item in error.errors()[:5]:
            field = ".".join(str(part) for part in item.get("loc", ())) or "поля"
            problems.append(f"{field}: {item.get('msg')}")
        return "; ".join(problems)
    return str(error)


class AIProcessor:
    """Извлекает структурированные данные из расшифровки диалога."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        timeout: float = 90.0,
        retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.retries = max(0, retries)

    # ------------------------------------------------------------ сеть

    def _call(self, messages: list[dict]) -> tuple[str, dict]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_error = AIProcessorError("запрос не выполнен")

        for attempt in range(self.retries + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                last_error = AIProcessorError(f"сеть: {exc}")
            else:
                if response.status_code == 200:
                    data = response.json()
                    message = ((data.get("choices") or [{}])[0]).get("message") or {}
                    return (message.get("content") or "").strip(), data.get("usage") or {}
                last_error = AIProcessorError(f"{response.status_code}: {response.text[:300]}")
                if response.status_code != 429 and response.status_code < 500:
                    raise last_error
            if attempt < self.retries:
                time.sleep(1.5 ** attempt)

        raise last_error

    # ------------------------------------------------------------ работа

    def process(self, dialog: str) -> tuple[ReportData, dict]:
        """Вернуть данные отчёта и статистику."""
        started = time.perf_counter()
        meta: dict[str, Any] = {
            "attempts": 0,
            "repaired": False,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "raw": "",
        }

        raw = ""
        try:
            raw, usage = self._call(build_messages(dialog))
            meta["attempts"] += 1
            self._add_usage(meta, usage)
            data = ReportData(**extract_json_object(raw))
        except (AIProcessorError, ValidationError) as exc:
            first_error = _describe_error(exc)
            logger.warning("первый ответ не подошёл: %s", first_error)
            meta["repaired"] = True

            try:
                fixed, usage = self._call(repair_messages(dialog, raw, first_error))
                meta["attempts"] += 1
                self._add_usage(meta, usage)
                data = ReportData(**extract_json_object(fixed))
                meta["raw"] = fixed
            except (AIProcessorError, ValidationError) as second:
                raise AIProcessorError(
                    "модель не дала корректный JSON даже после повтора: "
                    f"{first_error} → {_describe_error(second)}"
                ) from second
        else:
            meta["raw"] = raw

        meta["seconds"] = round(time.perf_counter() - started, 2)
        return data, meta

    @staticmethod
    def _add_usage(meta: dict, usage: dict) -> None:
        meta["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        meta["completion_tokens"] += int(usage.get("completion_tokens") or 0)