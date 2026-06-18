import asyncio
import base64
import html
import json
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


API_BASE = "https://api.mihomo.me/sr_info_parsed"
ASSET_BASE = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
UID_PATTERN = re.compile(r"(?:uid|UID|星铁|崩铁|星穹|开拓者|查|查询|profile|资料)[^\d]{0,24}(\d{8,10})")


def _asset(path: Optional[str]) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return ASSET_BASE + path.lstrip("/")


def _json_script(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _retryable_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or 500 <= status_code <= 599


def _retry_delay(attempt: int) -> float:
    return min(1.5 * (2 ** (attempt - 1)), 12)


def _normalize_uid(uid: str) -> str:
    cleaned = "".join(ch for ch in str(uid) if ch.isdigit())
    if not cleaned:
        raise ValueError("请提供有效的 UID。")
    return cleaned


def _field_value(character: dict, fields: list[str]) -> str:
    values = []
    values.extend(character.get("attributes") or [])
    values.extend(character.get("additions") or [])
    values.extend(character.get("statistics") or [])
    for field in fields:
        for item in values:
            if item.get("field") == field or item.get("name") == field:
                return str(item.get("display") or item.get("value") or "-")
    return "-"


def fetch_profile(
    uid: str,
    lang: str = "cn",
    timeout: int = 30,
    retries: int = 5,
    proxy: Optional[str] = None,
    use_env_proxy: bool = False,
) -> dict:
    session = requests.Session()
    session.trust_env = use_env_proxy
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    max_retries = max(0, min(int(retries), 5))
    params = {"lang": lang}
    headers = {"Accept": "application/json", "User-Agent": "astrbot-plugin-starrail-profile/1.0"}
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            response = session.get(f"{API_BASE}/{uid}", params=params, headers=headers, timeout=timeout)
            if response.status_code >= 400:
                if _retryable_status(response.status_code) and attempt < max_retries:
                    raise requests.HTTPError(f"接口返回 {response.status_code}", response=response)
                response.raise_for_status()

            data = response.json()
            if "player" not in data:
                raise ValueError("接口响应里没有 player 字段，可能 UID 不存在或数据格式变化。")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                if not _retryable_status(exc.response.status_code):
                    break
            if attempt >= max_retries:
                break
            time.sleep(_retry_delay(attempt + 1))

    raise RuntimeError(f"请求失败，已重试 {max_retries} 次：{last_error}")


def build_report_html(data: dict) -> str:
    player = data.get("player") or {}
    characters = data.get("characters") or []
    featured = sorted(characters, key=lambda item: (item.get("pos") or [99])[0])[:8]
    top = featured[0] if featured else {}
    info = player.get("space_info") or {}
    memory = info.get("memory_data") or {}
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    hero = _asset(top.get("portrait") or top.get("preview") or player.get("avatar", {}).get("icon"))
    avatar = _asset(player.get("avatar", {}).get("icon") or top.get("icon"))

    def stat(label: str, value: Any, note: str = "") -> str:
        return f"""
        <article class="stat">
          <div class="label">{html.escape(label)}</div>
          <div class="value">{html.escape(str(value if value is not None else "-"))}</div>
          <div class="note">{html.escape(note)}</div>
        </article>
        """

    def tag(label: Optional[str], icon: Optional[str] = None) -> str:
        if not label:
            return ""
        icon_html = f'<img src="{_asset(icon)}" alt="">' if icon else ""
        return f'<span class="tag">{icon_html}{html.escape(str(label))}</span>'

    def card(character: dict) -> str:
        element = character.get("element") or {}
        path = character.get("path") or {}
        cone = character.get("light_cone") or {}
        stats = [
            ("生命", _field_value(character, ["hp", "生命值", "HP"])),
            ("攻击", _field_value(character, ["atk", "攻击力", "ATK"])),
            ("速度", _field_value(character, ["spd", "速度", "SPD"])),
            ("暴击", _field_value(character, ["crit_rate", "暴击率", "CRIT Rate"])),
            ("暴伤", _field_value(character, ["crit_dmg", "暴击伤害", "CRIT DMG"])),
            ("击破", _field_value(character, ["break_dmg", "击破特攻", "Break Effect"])),
        ]
        mini = "".join(f'<div class="mini"><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>' for k, v in stats)
        pos = ", ".join(map(str, character.get("pos") or [])) or "-"
        preview = _asset(character.get("preview") or character.get("portrait") or character.get("icon"))
        fallback = _asset(character.get("icon") or character.get("preview") or character.get("portrait"))
        cone_icon = _asset(cone.get("icon"))
        cone_name = html.escape(str(cone.get("name") or "未装备光锥"))
        cone_meta = f"{'★' * int(cone.get('rarity') or 0)} / Lv.{cone.get('level', '-')} / 叠影 {cone.get('rank', '-')}" if cone else "暂无公开数据"
        return f"""
        <article class="card">
          <div class="art"><img src="{preview}" data-fallback="{fallback}" onerror="this.onerror=null;this.src=this.dataset.fallback" alt=""></div>
          <div class="body">
            <div class="top"><div><h3>{html.escape(str(character.get("name") or "未知角色"))}</h3><p>Lv.{character.get("level", "-")} / 星魂 {character.get("rank", 0)} / 晋阶 {character.get("promotion", "-")}</p></div><em>{'★' * int(character.get('rarity') or 0)}</em></div>
            <div class="tags">{tag(element.get("name"), element.get("icon"))}{tag(path.get("name"), path.get("icon"))}{tag("展位 " + pos)}</div>
            <div class="miniGrid">{mini}</div>
            <div class="cone">{f'<img src="{cone_icon}" alt="">' if cone_icon else '<span></span>'}<div><strong>{cone_name}</strong><small>{html.escape(cone_meta)}</small></div></div>
          </div>
        </article>
        """

    cards = "".join(card(character) for character in featured)
    stats = "".join(
        [
            stat("开拓等级", player.get("level"), f"UID {player.get('uid', '-')}"),
            stat("均衡等级", player.get("world_level"), f"{player.get('friend_count', 0)} 位好友"),
            stat("角色收集", info.get("avatar_count", len(characters)), f"{len(characters)} 位展示"),
            stat("混沌星数", memory.get("chaos_star_count", "-"), f"层数 {memory.get('chaos_level', memory.get('level', '-'))}"),
            stat("模拟宇宙", info.get("universe_level", "-"), "最高挑战记录"),
            stat("光锥", info.get("light_cone_count", "-"), "公开统计"),
            stat("遗器", info.get("relic_count", "-"), "公开统计"),
            stat("成就", info.get("achievement_count", "-"), f"书籍 {info.get('book_count', '-')} / 音乐 {info.get('music_count', '-')}"),
        ]
    )
    payload = _json_script(data)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1080, initial-scale=1">
<title>Star Rail Profile</title>
<style>
*{{box-sizing:border-box}}html,body{{width:1080px;height:1920px;margin:0;overflow:hidden;font-family:"Microsoft YaHei","Segoe UI",sans-serif;color:#25283d}}body{{background:radial-gradient(circle at 8% 8%,rgba(255,112,171,.26),transparent 28%),radial-gradient(circle at 95% 3%,rgba(71,199,253,.26),transparent 31%),linear-gradient(140deg,#fff2fa 0%,#eefaff 46%,#fff8df 100%)}}body:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.55) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.55) 1px,transparent 1px);background-size:40px 40px}}.poster{{position:relative;width:1080px;height:1920px;padding:36px 46px 72px}}.hero{{height:418px;border:2px solid rgba(255,255,255,.74);border-radius:18px;background:linear-gradient(110deg,rgba(32,34,62,.9),rgba(41,43,78,.7) 48%,rgba(255,255,255,.28)),url("{hero}") right -16px bottom -42px/auto 488px no-repeat;box-shadow:0 30px 80px rgba(58,46,88,.24);color:white;overflow:hidden;position:relative}}.hero:before{{content:"";position:absolute;inset:16px;border:1px solid rgba(255,255,255,.22);border-radius:14px}}.avatar{{position:absolute;right:36px;top:34px;width:104px;height:104px;border:6px solid white;border-radius:18px;background:#fff;overflow:hidden;box-shadow:0 18px 36px rgba(17,20,42,.24)}}.avatar img{{width:100%;height:100%;object-fit:cover}}.copy{{position:relative;z-index:2;width:610px;padding:38px 44px}}.kicker{{display:inline-flex;padding:7px 14px;border-radius:999px;background:rgba(255,255,255,.2);font-size:17px;font-weight:900}}h1{{margin:18px 0 10px;font-size:68px;line-height:.95;color:white}}.sig{{min-height:62px;font-size:23px;line-height:1.38;color:rgba(255,255,255,.9)}}.pills{{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}}.pill{{padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.2);font-size:18px;font-weight:900}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}}.stat{{height:122px;padding:15px 18px;border-radius:16px;border:1px solid rgba(255,255,255,.72);background:rgba(255,255,255,.78);box-shadow:0 18px 42px rgba(56,49,83,.12)}}.label{{color:#747994;font-size:16px;font-weight:900}}.value{{margin-top:6px;color:#292d47;font-size:38px;line-height:1;font-weight:1000}}.note{{margin-top:6px;color:#8c91aa;font-size:14px;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.head{{display:flex;justify-content:space-between;align-items:end;margin:26px 2px 14px}}.head h2{{margin:0;font-size:34px}}.head span{{color:#777d98;font-size:18px;font-weight:850}}.cards{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.card{{height:232px;display:grid;grid-template-columns:126px minmax(0,1fr);overflow:hidden;border-radius:18px;border:1px solid rgba(255,255,255,.78);background:linear-gradient(145deg,rgba(255,255,255,.92),rgba(255,255,255,.68));box-shadow:0 18px 46px rgba(56,49,83,.13)}}.art{{display:flex;align-items:flex-start;justify-content:center;overflow:hidden;background:linear-gradient(to top,rgba(39,42,72,.48),transparent 58%),linear-gradient(155deg,rgba(255,123,189,.18),rgba(88,215,255,.11))}}.art img{{height:252px;width:190px;object-fit:cover;object-position:center 18%;transform:translateY(-16px);filter:drop-shadow(0 14px 20px rgba(25,28,50,.22))}}.body{{padding:14px 16px;min-width:0}}.top{{display:flex;justify-content:space-between;gap:10px}}h3{{margin:0;font-size:25px;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}p{{margin:5px 0 0;color:#707690;font-size:14px;font-weight:900}}em{{font-style:normal;padding:6px 9px;border-radius:999px;background:linear-gradient(135deg,#ffd36e,#ff7bbd);font-size:14px;font-weight:1000}}.tags{{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}}.tag{{display:inline-flex;align-items:center;gap:6px;height:28px;max-width:150px;padding:0 9px;border-radius:999px;background:rgba(255,255,255,.72);border:1px solid rgba(95,106,150,.13);font-size:13px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.tag img{{width:18px;height:18px;object-fit:contain}}.miniGrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:10px}}.mini{{height:48px;padding:7px 8px;border-radius:12px;background:rgba(255,255,255,.64);border:1px solid rgba(95,106,150,.12)}}.mini span{{display:block;color:#8a8fa8;font-size:12px;font-weight:900}}.mini b{{display:block;margin-top:4px;font-size:18px;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.cone{{display:grid;grid-template-columns:44px minmax(0,1fr);gap:9px;align-items:center;margin-top:10px;padding:7px;border-radius:12px;background:rgba(37,41,70,.08);border:1px solid rgba(95,106,150,.12)}}.cone img{{width:44px;height:44px;border-radius:10px;object-fit:cover}}.cone strong,.cone small{{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.cone strong{{font-size:15px}}.cone small{{margin-top:4px;color:#777d99;font-size:13px;font-weight:850}}.footer{{position:absolute;left:46px;right:46px;bottom:28px;display:flex;justify-content:space-between;color:#747994;font-size:16px;font-weight:850}}.footer b{{color:#ca477d}}
</style>
</head>
<body>
<main class="poster">
  <section class="hero"><div class="avatar"><img src="{avatar}" data-fallback="{avatar}" alt=""></div><div class="copy"><span class="kicker">Star Rail Showcase Report</span><h1>{html.escape(str(player.get("nickname") or "未知开拓者"))}</h1><div class="sig">{html.escape(str(player.get("signature") or "这位开拓者还没有留下签名。"))}</div><div class="pills"><span class="pill">UID {html.escape(str(player.get("uid", "-")))}</span><span class="pill">开拓等级 {html.escape(str(player.get("level", "-")))}</span><span class="pill">均衡 {html.escape(str(player.get("world_level", "-")))}</span><span class="pill">{len(characters)} 位展示角色</span></div></div></section>
  <section class="summary">{stats}</section>
  <div class="head"><h2>展示角色阵容</h2><span>TOP {len(featured)} / {len(characters)}</span></div>
  <section class="cards">{cards}</section>
  <footer class="footer"><span>Generated by <b>astrbot_plugin_starrail_profile</b></span><span>{generated_at}</span></footer>
</main>
<script>window.REPORT_DATA={payload};</script>
</body>
</html>"""


async def render_html_to_png(html_path: Path, output_path: Path, width: int, height: int, timeout: int, browser_channel: Optional[str]) -> Path:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("缺少 playwright 依赖，请先安装：pip install playwright") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = None
        try:
            if browser_channel:
                browser = await playwright.chromium.launch(headless=True, channel=browser_channel)
            else:
                try:
                    browser = await playwright.chromium.launch(headless=True)
                except Exception:
                    for channel in ("chrome", "msedge"):
                        try:
                            browser = await playwright.chromium.launch(headless=True, channel=channel)
                            break
                        except Exception:
                            continue
            if browser is None:
                raise RuntimeError("Playwright Chromium 启动失败，请执行：python -m playwright install chromium")

            page = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            page.set_default_timeout(timeout * 1000)
            page.set_default_navigation_timeout(timeout * 1000)
            await page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout * 1000, 10000))
            except Exception:
                pass
            await page.evaluate(
                """
                async (timeout) => {
                  const urls = Array.from(new Set(Array.from(document.images).map((img) => img.currentSrc || img.src).filter(Boolean)));
                  const waitUrl = (url) => new Promise((resolve) => {
                    const img = new Image();
                    img.onload = resolve;
                    img.onerror = resolve;
                    img.src = url;
                    if (img.complete) resolve();
                  });
                  await Promise.race([
                    Promise.all(urls.map(waitUrl)),
                    new Promise((resolve) => setTimeout(resolve, timeout))
                  ]);
                  document.querySelectorAll("img[data-fallback]").forEach((img) => {
                    if (!img.complete || img.naturalWidth === 0) img.src = img.dataset.fallback;
                  });
                }
                """,
                min(timeout * 1000, 15000),
            )
            await page.wait_for_timeout(600)
            session = await page.context.new_cdp_session(page)
            screenshot = await session.send(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
                    "captureBeyondViewport": False,
                },
            )
            output_path.write_bytes(base64.b64decode(screenshot["data"]))
        finally:
            if browser is not None:
                await browser.close()

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Playwright 没有生成有效 PNG 文件。")
    return output_path


@register("astrbot_plugin_starrail_profile", "YueHua46", "根据星穹铁道 UID 生成二次元风格展示柜 Profile 图片。", "1.0.1")
class StarRailProfilePlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

    @filter.command("srprofile")
    async def srprofile(self, event: AstrMessageEvent, uid: str):
        """查询星穹铁道 UID 展示柜报告。用法：/srprofile 100534214"""
        async for result in self._send_profile(event, uid):
            yield result

    @filter.command("sr")
    async def sr(self, event: AstrMessageEvent, uid: str):
        """查询星穹铁道 UID 展示柜报告。用法：/sr 100534214"""
        async for result in self._send_profile(event, uid):
            yield result

    @filter.regex(r"(?:uid|UID|星铁|崩铁|星穹|开拓者|查|查询|profile|资料)[^\d]{0,24}\d{8,10}")
    async def natural_query(self, event: AstrMessageEvent):
        """自然语言触发，例如：帮我查一下星铁 UID 100534214。"""
        match = UID_PATTERN.search(event.message_str or "")
        if not match:
            return
        async for result in self._send_profile(event, match.group(1)):
            yield result

    async def _send_profile(self, event: AstrMessageEvent, uid: str):
        uid = _normalize_uid(uid)
        yield event.plain_result(f"正在生成 UID {uid} 的星穹铁道 Profile 图片...")
        try:
            image_path = await self._create_report(uid)
            yield event.image_result(str(image_path))
        except Exception as exc:
            logger.exception("生成星穹铁道 Profile 图片失败")
            yield event.plain_result(f"生成失败：{exc}")

    async def _create_report(self, uid: str) -> Path:
        data = await asyncio.to_thread(
            fetch_profile,
            uid,
            str(self.config.get("lang") or "cn"),
            int(self.config.get("timeout") or 30),
            int(self.config.get("retries") or 5),
            self.config.get("proxy") or None,
            bool(self.config.get("use_env_proxy") or False),
        )
        output_dir = Path(self.config.get("output_dir") or "data/starrail_profile_reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        player_uid = str((data.get("player") or {}).get("uid") or uid)
        image_path = output_dir / f"starrail_report_{player_uid}.png"
        html_path = Path(tempfile.gettempdir()) / f"starrail_report_{player_uid}.html"
        html_path.write_text(build_report_html(data), encoding="utf-8")
        await render_html_to_png(
            html_path,
            image_path,
            int(self.config.get("width") or 1080),
            int(self.config.get("height") or 1920),
            int(self.config.get("screenshot_timeout") or 120),
            self.config.get("browser_channel") or None,
        )
        if not bool(self.config.get("keep_html") or False):
            html_path.unlink(missing_ok=True)
        return image_path

    async def initialize(self):
        logger.info("astrbot_plugin_starrail_profile initialized")

    async def terminate(self):
        logger.info("astrbot_plugin_starrail_profile terminated")
