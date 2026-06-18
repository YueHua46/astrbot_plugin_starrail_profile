import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import StarRailClient
from .renderer import PlaywrightRenderer
from .template import write_report_html


@dataclass(slots=True)
class ReportResult:
    image_path: Path
    html_path: Path
    data: dict[str, Any]


@dataclass(slots=True)
class StarRailReportService:
    output_dir: Path
    lang: str = "cn"
    timeout: int = 30
    retries: int = 5
    proxy: str | None = None
    use_env_proxy: bool = False
    screenshot_timeout: int = 120
    width: int = 1080
    height: int = 1920
    browser_channel: str | None = None
    keep_html: bool = False

    async def create_report(self, uid: str, force: bool = False) -> ReportResult:
        normalized_uid = self.normalize_uid(uid)
        client = StarRailClient(
            lang=self.lang,
            timeout=self.timeout,
            retries=self.retries,
            proxy=self.proxy,
            use_env_proxy=self.use_env_proxy,
        )
        data = await asyncio.to_thread(client.fetch_profile, normalized_uid, force)
        player_uid = str(data.get("player", {}).get("uid") or normalized_uid)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        image_path = self.output_dir / f"starrail_report_{player_uid}.png"
        if self.keep_html:
            html_path = self.output_dir / f"starrail_report_{player_uid}.html"
        else:
            html_path = Path(tempfile.gettempdir()) / f"starrail_report_{player_uid}.html"

        await asyncio.to_thread(write_report_html, data, html_path)
        renderer = PlaywrightRenderer(
            width=self.width,
            height=self.height,
            timeout=self.screenshot_timeout,
            browser_channel=self.browser_channel,
        )
        await renderer.screenshot_html(html_path, image_path)

        if not self.keep_html:
            html_path.unlink(missing_ok=True)

        return ReportResult(image_path=image_path, html_path=html_path, data=data)

    @staticmethod
    def normalize_uid(uid: str) -> str:
        cleaned = "".join(ch for ch in str(uid) if ch.isdigit())
        if not cleaned:
            raise ValueError("请提供有效的 UID。")
        return cleaned
