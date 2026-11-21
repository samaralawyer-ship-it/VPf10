"""Имена файлов и сохранение результатов."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.models import ReportData


def make_stamp(moment: datetime | None = None) -> str:
    return (moment or datetime.now()).strftime("%Y-%m-%d_%H-%M")


def report_paths(reports_dir: Path, report_type: str, stamp: str) -> tuple[Path, Path]:
    base = f"report_{stamp}_{report_type}"
    return reports_dir / f"{base}.pdf", reports_dir / f"{base}.json"


def save_json(data: ReportData, meta: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "meta": {key: value for key, value in meta.items() if key != "raw"},
        "data": data.model_dump(),
        "missing": data.missing_fields(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")