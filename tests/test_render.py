"""Тесты рендера HTML и сборки PDF."""

from pathlib import Path

import pytest

from app.models import ReportData
from app.pdf_generator import PdfError, build_pdf, render_html

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def sample(**overrides):
    base = {
        "client_name": "Иван Петров",
        "contact": "+7 987 000-11-22",
        "country": "Турция",
        "city": "Анталья",
        "dates": "10–17 июля",
        "nights": 7,
        "people": 3,
        "budget": 150000,
        "preferences": ["всё включено", "первая линия"],
        "topic": "подбор тура",
        "main_request": "Нужен тур на неделю с ребёнком.",
        "mood": "заинтересованное",
        "risks": ["бюджет под вопросом"],
        "next_steps": ["подготовить три варианта"],
        "manager": "Анна",
        "confidence": 0.8,
    }
    base.update(overrides)
    return ReportData(**base)


@pytest.mark.parametrize("report_type", ["request", "summary"])
def test_render_contains_data(report_type):
    html = render_html(sample(), report_type, TEMPLATES, "17.11.2026 09:00")
    assert "Иван Петров" in html
    assert "150 000 ₽" in html
    assert "Анталья" in html


def test_render_shows_missing_block():
    html = render_html(sample(budget=None, city=""), "request", TEMPLATES, "17.11.2026 09:00")
    assert "Уточнить у клиента" in html
    assert "бюджет" in html


def test_render_unknown_type():
    with pytest.raises(PdfError):
        render_html(sample(), "unknown", TEMPLATES, "17.11.2026 09:00")


def test_build_pdf_creates_file(tmp_path):
    out = tmp_path / "report.pdf"
    size, seconds = build_pdf(sample(), "request", out, TEMPLATES, "17.11.2026 09:00")

    assert out.exists()
    assert size > 5000
    assert seconds >= 0