"""Тесты схемы отчёта."""

import pytest
from pydantic import ValidationError

from app.models import NOT_SPECIFIED, ReportData


def full_data(**overrides):
    base = {
        "client_name": "Иван",
        "contact": "+7 987 000-11-22",
        "country": "Турция",
        "city": "Анталья",
        "dates": "10–17 июля",
        "nights": 7,
        "people": 3,
        "budget": 150000,
        "preferences": ["всё включено", "первая линия"],
        "topic": "подбор тура",
        "main_request": "Нужен тур в Анталью на неделю с ребёнком.",
        "mood": "заинтересованное",
        "risks": ["бюджет под вопросом"],
        "next_steps": ["подготовить три варианта"],
        "manager": "Анна",
        "confidence": 0.8,
    }
    base.update(overrides)
    return base


def test_valid_data_accepted():
    data = ReportData(**full_data())
    assert data.country == "Турция"
    assert data.nights == 7
    assert data.budget == 150000
    assert data.confidence == 0.8


def test_budget_from_words():
    data = ReportData(**full_data(budget="сто пятьдесят тысяч"))
    assert data.budget is None


def test_budget_with_spaces_and_rubles():
    data = ReportData(**full_data(budget="150 000 ₽"))
    assert data.budget == 150000


def test_nights_from_text():
    data = ReportData(**full_data(nights="7 ночей"))
    assert data.nights == 7


@pytest.mark.parametrize("value", [0, -3, "не указано", None, ""])
def test_nights_meaningless_becomes_none(value):
    data = ReportData(**full_data(nights=value))
    assert data.nights is None


@pytest.mark.parametrize("field,value", [("nights", 61), ("people", 25), ("confidence", 2)])
def test_out_of_bounds_rejected(field, value):
    with pytest.raises(ValidationError):
        ReportData(**full_data(**{field: value}))


def test_empty_client_name_becomes_not_specified():
    data = ReportData(**full_data(client_name="   "))
    assert data.client_name == NOT_SPECIFIED
    assert "имя клиента" in data.missing_fields()


def test_lists_are_trimmed_and_cleaned():
    data = ReportData(
        **full_data(
            preferences=["всё включено", "", "   ", "аквапарк"] + [f"п{i}" for i in range(10)],
            risks="сжатые сроки",
        )
    )
    assert data.preferences[0] == "всё включено"
    assert data.preferences[1] == "аквапарк"
    assert len(data.preferences) == 6
    assert data.risks == ["сжатые сроки"]


def test_extra_fields_ignored():
    data = ReportData(**full_data(unknown_field="значение"))
    assert not hasattr(data, "unknown_field")


def test_missing_fields_detected():
    data = ReportData()
    missing = data.missing_fields()
    assert "страна" in missing
    assert "бюджет" in missing
    assert "контакт клиента" in missing


def test_missing_fields_empty_for_full_data():
    data = ReportData(**full_data())
    assert data.missing_fields() == []


def test_budget_and_trip_text():
    data = ReportData(**full_data())
    assert data.budget_text() == "150 000 ₽"
    assert data.trip_text() == "7 ночей, 3 чел."


def test_defaults_for_empty_model_answer():
    data = ReportData(client_name="Иван", country="", city="не указано")
    assert data.country == NOT_SPECIFIED
    assert data.city == NOT_SPECIFIED
    assert data.budget is None