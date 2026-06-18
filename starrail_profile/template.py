import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "report_template.html"


def build_report_html(
    data: dict[str, Any],
    template_path: Path = DEFAULT_TEMPLATE,
    generated_at: datetime | None = None,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    timestamp = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    return template.replace("__REPORT_DATA__", payload).replace("__GENERATED_AT__", timestamp)


def write_report_html(
    data: dict[str, Any],
    html_path: Path,
    template_path: Path = DEFAULT_TEMPLATE,
) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(build_report_html(data, template_path), encoding="utf-8")
    return html_path
