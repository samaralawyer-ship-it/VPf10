"""Рендер HTML по шаблону и конвертация в PDF."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import weasyprint
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import ReportData

logger = logging.getLogger(__name__)

TEMPLATES = {"request": "request.html", "summary": "summary.html"}


class PdfError(RuntimeError):
    """Не удалось собрать PDF."""


def render_html(
    data: ReportData, report_type: str, templates_dir: Path, generated_at: str
) -> str:
    template_name = TEMPLATES.get(report_type)
    if template_name is None:
        raise PdfError(f"неизвестный тип отчёта: {report_type}")

    environment = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(template_name)
    return template.render(
        d=data,
        missing=data.missing_fields(),
        budget=data.budget_text(),
        trip=data.trip_text(),
        generated_at=generated_at,
        report_type=report_type,
    )


def html_to_pdf(html: str, path: Path) -> int:
    try:
        weasyprint.HTML(string=html).write_pdf(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"WeasyPrint не смог собрать PDF: {exc}") from exc
    if not path.exists() or path.stat().st_size == 0:
        raise PdfError("PDF не создан или получился пустым")
    return path.stat().st_size


def build_pdf(
    data: ReportData,
    report_type: str,
    out_path: Path,
    templates_dir: Path,
    generated_at: str,
) -> tuple[int, float]:
    """Собрать PDF. Вернуть размер в байтах и время в секундах."""
    started = time.perf_counter()
    html = render_html(data, report_type, templates_dir, generated_at)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    size = html_to_pdf(html, out_path)
    seconds = round(time.perf_counter() - started, 2)
    logger.debug("PDF собран: %s байт за %s с", size, seconds)
    return size, seconds