import re
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from starrail_profile.service import StarRailReportService


UID_PATTERN = re.compile(r"(?:uid|UID|星铁|崩铁|星穹|开拓者|查|查询|profile|资料)[^\d]{0,24}(\d{8,10})")


@register(
    "astrbot_plugin_starrail_profile",
    "DIANCHEN",
    "根据星穹铁道 UID 生成二次元风格展示柜 Profile 图片。",
    "1.0.0",
)
class StarRailProfilePlugin(Star):
    def __init__(self, context: Context, config: dict[str, Any] | None = None):
        super().__init__(context)
        self.config = config or {}

    @filter.command("srprofile")
    async def srprofile(self, event: AstrMessageEvent, uid: str):
        """查询星穹铁道 UID 展示柜报告。用法：/srprofile 100534214"""
        async for result in self._build_profile_results(event, uid):
            yield result

    @filter.command("sr")
    async def sr(self, event: AstrMessageEvent, uid: str):
        """查询星穹铁道 UID 展示柜报告。用法：/sr 100534214"""
        async for result in self._build_profile_results(event, uid):
            yield result

    @filter.regex(r"(?:uid|UID|星铁|崩铁|星穹|开拓者|查|查询|profile|资料)[^\d]{0,24}\d{8,10}")
    async def natural_query(self, event: AstrMessageEvent):
        """自然语言触发，例如：帮我查一下星铁 UID 100534214。"""
        message = getattr(event, "message_str", "") or ""
        match = UID_PATTERN.search(message)
        if not match:
            return
        async for result in self._build_profile_results(event, match.group(1)):
            yield result

    @filter.llm_tool(name="query_starrail_profile")
    async def query_starrail_profile(self, event: AstrMessageEvent, uid: str) -> str:
        """根据星穹铁道 UID 生成 Profile 图片，并返回图片路径。"""
        service = self._service()
        result = await service.create_report(uid)
        return f"已生成星穹铁道 UID {uid} 的 Profile 图片：{result.image_path}"

    async def _build_profile_results(self, event: AstrMessageEvent, uid: str):
        yield event.plain_result(f"正在生成 UID {uid} 的星穹铁道 Profile 图片...")
        try:
            service = self._service()
            result = await service.create_report(uid)
            yield event.image_result(str(result.image_path))
        except Exception as exc:
            logger.exception("生成星穹铁道 Profile 图片失败")
            yield event.plain_result(f"生成失败：{exc}")

    def _service(self) -> StarRailReportService:
        output_dir = Path(self.config.get("output_dir") or "data/starrail_profile_reports")
        return StarRailReportService(
            output_dir=output_dir,
            lang=str(self.config.get("lang") or "cn"),
            timeout=int(self.config.get("timeout") or 30),
            retries=int(self.config.get("retries") or 5),
            proxy=self.config.get("proxy") or None,
            use_env_proxy=bool(self.config.get("use_env_proxy") or False),
            screenshot_timeout=int(self.config.get("screenshot_timeout") or 120),
            width=int(self.config.get("width") or 1080),
            height=int(self.config.get("height") or 1920),
            browser_channel=self.config.get("browser_channel") or None,
            keep_html=bool(self.config.get("keep_html") or False),
        )
