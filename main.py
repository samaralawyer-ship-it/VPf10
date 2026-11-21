"""CLI: расшифровка диалога → JSON → PDF-отчёт."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from app.ai_processor import AIProcessor, AIProcessorError
from app.config import settings
from app.pdf_generator import TEMPLATES, PdfError, build_pdf
from app.reports import make_stamp, report_paths, save_json

logger = logging.getLogger("reports")


class InputError(ValueError):
    """Ошибка входных данных: код возврата 2."""


def setup_logging(quiet: bool) -> None:
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    console.setLevel(logging.WARNING if quiet else logging.INFO)

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(settings.reports_dir.parent / "app.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    file_handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for noisy in ("weasyprint", "fontTools", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    for handler in (console, file_handler):
        root.addHandler(handler)


def read_dialog(args: argparse.Namespace) -> tuple[str, str]:
    if args.interactive:
        print("Вставьте текст диалога. Пустая строка или END — конец ввода.")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip().upper() in ("END", ""):
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        if not text:
            raise InputError("пустой ввод")
        return text, "ввод с клавиатуры"

    if not args.dialog:
        raise InputError("укажите файл с диалогом или используйте --interactive")

    path = Path(args.dialog)
    if not path.exists():
        raise InputError(f"файл не найден: {path}")
    if path.stat().st_size == 0:
        raise InputError(f"файл пустой: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"файл не в кодировке UTF-8: {path}") from exc

    text = text.strip()
    if not text:
        raise InputError(f"в файле нет текста: {path}")
    return text, str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Генератор PDF-отчётов из расшифровок диалогов с клиентами"
    )
    parser.add_argument("dialog", nargs="?", help="файл с расшифровкой (txt, UTF-8)")
    parser.add_argument("--type", choices=sorted(TEMPLATES), default="request", help="тип отчёта")
    parser.add_argument("--out", help="каталог для результатов (по умолчанию reports/)")
    parser.add_argument("--json-only", action="store_true", help="только JSON, без PDF")
    parser.add_argument("--interactive", action="store_true", help="ввести текст вручную")
    parser.add_argument("--model", help="модель (переопределяет .env)")
    parser.add_argument("--quiet", action="store_true", help="меньше логов")
    args = parser.parse_args(argv)

    setup_logging(args.quiet)

    try:
        settings.validate()
        text, source = read_dialog(args)
        if len(text) > settings.max_input_chars:
            raise InputError(
                f"текст длиннее {settings.max_input_chars} символов: {len(text)}"
            )
    except (InputError, ValueError) as exc:
        logger.error("Ошибка ввода: %s", exc)
        return 2

    logger.info("[1/4] чтение: %s (%s символов)", source, len(text))

    model = args.model or settings.chat_model
    processor = AIProcessor(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=model,
        temperature=settings.chat_temperature,
        timeout=settings.request_timeout,
        retries=settings.retries,
    )

    logger.info("[2/4] запрос к модели: %s", model)
    try:
        data, meta = processor.process(text)
    except AIProcessorError as exc:
        logger.error("Модель не дала корректных данных: %s", exc)
        return 1

    logger.info(
        "      ответ: токены %s/%s, %s с, попыток: %s",
        meta["prompt_tokens"],
        meta["completion_tokens"],
        meta["seconds"],
        meta["attempts"],
    )
    if meta["repaired"]:
        logger.warning("      был повтор: первый ответ не прошёл проверку")

    missing = data.missing_fields()
    logger.info(
        "[3/4] валидация: успешно, пропущено полей: %s%s",
        len(missing),
        f" ({', '.join(missing)})" if missing else "",
    )

    if args.json_only:
        print(json.dumps(data.model_dump(), ensure_ascii=False, indent=2))
        return 0

    out_dir = Path(args.out) if args.out else settings.reports_dir
    pdf_path, json_path = report_paths(out_dir, args.type, make_stamp())
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    try:
        size, seconds = build_pdf(data, args.type, pdf_path, settings.templates_dir, generated_at)
    except PdfError as exc:
        logger.error("Не удалось собрать PDF: %s", exc)
        return 1

    save_json(data, meta, json_path)
    logger.info("[4/4] PDF: %s (%s КБ), %s с", pdf_path, round(size / 1024), seconds)
    print(f"Отчёт создан: {pdf_path}")
    print(f"Данные: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())