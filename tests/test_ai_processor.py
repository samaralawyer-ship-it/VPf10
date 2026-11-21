"""Тесты разбора JSON и повтора при ошибке."""

import pytest
from pydantic import ValidationError

from app.ai_processor import AIProcessor, AIProcessorError, extract_json_object


def test_extract_plain_json():
    assert extract_json_object('{"client_name": "Иван"}') == {"client_name": "Иван"}


def test_extract_with_fence_and_text():
    raw = 'Вот данные:\n```json\n{"client_name": "Иван", "people": 2}\n```\nГотово.'
    assert extract_json_object(raw)["people"] == 2


def test_extract_nested_objects():
    raw = '{"client_name": "Иван", "extra": {"a": 1, "b": {"c": 2}}, "people": 2}'
    assert extract_json_object(raw)["extra"]["b"]["c"] == 2


def test_extract_object_with_braces_in_string():
    raw = '{"client_name": "Иван", "main_request": "хочет {срочно} тур"}'
    assert extract_json_object(raw)["main_request"] == "хочет {срочно} тур"


@pytest.mark.parametrize("raw", ["", "текст без json", '{"client_name": "Иван"'])
def test_extract_errors(raw):
    with pytest.raises(AIProcessorError):
        extract_json_object(raw)


def make_processor():
    return AIProcessor(api_key="k", base_url="https://example.test/v1", model="gpt-4o-mini")


def test_process_ok(monkeypatch):
    processor = make_processor()
    answers = iter([('{"client_name": "Иван", "nights": 7}', {"prompt_tokens": 10, "completion_tokens": 5})])
    monkeypatch.setattr(processor, "_call", lambda messages: next(answers))

    data, meta = processor.process("диалог")
    assert data.client_name == "Иван"
    assert data.nights == 7
    assert meta["attempts"] == 1
    assert meta["repaired"] is False
    assert meta["prompt_tokens"] == 10


def test_process_repairs_broken_json(monkeypatch):
    processor = make_processor()
    answers = iter(
        [
            ("не json", {"prompt_tokens": 10, "completion_tokens": 2}),
            ('{"client_name": "Иван"}', {"prompt_tokens": 12, "completion_tokens": 8}),
        ]
    )
    monkeypatch.setattr(processor, "_call", lambda messages: next(answers))

    data, meta = processor.process("диалог")
    assert data.client_name == "Иван"
    assert meta["attempts"] == 2
    assert meta["repaired"] is True
    assert meta["prompt_tokens"] == 22


def test_process_repairs_validation_error(monkeypatch):
    processor = make_processor()
    answers = iter(
        [
            ('{"client_name": "Иван", "confidence": 5}', {"prompt_tokens": 1, "completion_tokens": 1}),
            ('{"client_name": "Иван", "confidence": 0.5}', {"prompt_tokens": 1, "completion_tokens": 1}),
        ]
    )
    monkeypatch.setattr(processor, "_call", lambda messages: next(answers))

    data, meta = processor.process("диалог")
    assert data.confidence == 0.5
    assert meta["repaired"] is True


def test_process_raises_after_two_failures(monkeypatch):
    processor = make_processor()
    answers = iter(
        [
            ("мусор", {"prompt_tokens": 1, "completion_tokens": 1}),
            ("тоже мусор", {"prompt_tokens": 1, "completion_tokens": 1}),
        ]
    )
    monkeypatch.setattr(processor, "_call", lambda messages: next(answers))

    with pytest.raises(AIProcessorError):
        processor.process("диалог")


def test_repair_messages_contain_error():
    from app.prompts import repair_messages

    messages = repair_messages("диалог", "плохой ответ", "people: слишком много")
    assert messages[-1]["role"] == "user"
    assert "people: слишком много" in messages[-1]["content"]