import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from starrail_profile.renderer import PlaywrightRenderer
from starrail_profile.service import StarRailReportService
from starrail_profile.template import write_report_html


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"


DEMO_DATA = {
    "player": {
        "uid": "100000999",
        "nickname": "星海巡游者",
        "level": 70,
        "world_level": 6,
        "friend_count": 91,
        "avatar": {"id": "201006", "name": "Silver Wolf", "icon": "icon/avatar/1006.png"},
        "signature": "在群星之间，把每一张角色卡都排得漂漂亮亮。",
        "space_info": {
            "memory_data": {"level": 21, "chaos_level": 11, "chaos_star_count": 33},
            "universe_level": 9,
            "avatar_count": 41,
            "light_cone_count": 74,
            "relic_count": 1858,
            "achievement_count": 398,
            "book_count": 124,
            "music_count": 18,
        },
    },
    "characters": [
        {
            "id": "1212",
            "name": "镜流",
            "rarity": 5,
            "rank": 0,
            "level": 80,
            "promotion": 6,
            "icon": "icon/character/1212.png",
            "preview": "image/character_preview/1212.png",
            "portrait": "image/character_portrait/1212.png",
            "path": {"name": "毁灭", "icon": "icon/path/Destruction.png"},
            "element": {"name": "冰", "color": "#47C7FD", "icon": "icon/element/Ice.png"},
            "light_cone": {"name": "此身为剑", "rarity": 5, "rank": 1, "level": 80, "icon": "icon/light_cone/23014.png"},
            "attributes": [
                {"field": "hp", "name": "生命值", "display": "3250"},
                {"field": "atk", "name": "攻击力", "display": "2542"},
                {"field": "spd", "name": "速度", "display": "134"},
                {"field": "crit_rate", "name": "暴击率", "display": "48.5%"},
                {"field": "crit_dmg", "name": "暴击伤害", "display": "210.4%"},
                {"field": "break_dmg", "name": "击破特攻", "display": "-"},
            ],
            "pos": [0],
        }
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据星穹铁道 UID 生成 1080x1920 Profile 图片。")
    parser.add_argument("uid", nargs="?", help="星穹铁道 UID。使用 --demo 或 --json 时可省略。")
    parser.add_argument("--lang", default="cn", help="接口语言，默认 cn。")
    parser.add_argument("--output", "-o", type=Path, help="输出 PNG 路径，默认 reports/starrail_report_<uid>.png。")
    parser.add_argument("--json", type=Path, help="从本地 sr_info_parsed JSON 文件生成图片，不请求接口。")
    parser.add_argument("--demo", action="store_true", help="使用内置示例数据生成图片。")
    parser.add_argument("--force", action="store_true", help="请求接口时强制刷新缓存。")
    parser.add_argument("--proxy", help="请求接口使用的代理，例如 http://127.0.0.1:7890。")
    parser.add_argument("--use-env-proxy", action="store_true", help="允许 requests 使用系统环境代理。默认关闭。")
    parser.add_argument("--keep-html", action="store_true", help="保留渲染用 HTML 文件。")
    parser.add_argument("--html-output", type=Path, help="指定保留的 HTML 文件路径。")
    parser.add_argument("--width", type=int, default=1080, help="截图宽度，默认 1080。")
    parser.add_argument("--height", type=int, default=1920, help="截图高度，默认 1920。")
    parser.add_argument("--timeout", type=int, default=30, help="接口请求超时秒数，默认 30。")
    parser.add_argument("--screenshot-timeout", type=int, default=120, help="Playwright 截图超时秒数，默认 120。")
    parser.add_argument("--retries", type=int, default=5, help="请求失败后的最大重试次数，默认 5，最大 5。")
    parser.add_argument("--browser-channel", help="可选 Playwright 浏览器通道，例如 chrome、msedge。")
    return parser.parse_args()


async def render_existing_data(args: argparse.Namespace, data: dict, name: str) -> Path:
    uid = data.get("player", {}).get("uid") or name
    output = args.output or REPORT_DIR / f"starrail_report_{uid}.png"
    html_path = args.html_output or REPORT_DIR / f"starrail_report_{uid}.html"
    if not args.keep_html and not args.html_output:
        html_path = Path(tempfile.gettempdir()) / f"starrail_report_{uid}.html"

    await asyncio.to_thread(write_report_html, data, html_path)
    renderer = PlaywrightRenderer(
        width=args.width,
        height=args.height,
        timeout=args.screenshot_timeout,
        browser_channel=args.browser_channel,
    )
    await renderer.screenshot_html(html_path, output)
    if not args.keep_html and not args.html_output:
        html_path.unlink(missing_ok=True)
    return output


async def run() -> Path:
    args = parse_args()
    if args.demo:
        return await render_existing_data(args, DEMO_DATA, "demo")
    if args.json:
        data = json.loads(args.json.read_text(encoding="utf-8"))
        return await render_existing_data(args, data, args.json.stem)
    if not args.uid:
        raise ValueError("请传入 uid，或使用 --demo / --json。")

    service = StarRailReportService(
        output_dir=(args.output.parent if args.output else REPORT_DIR),
        lang=args.lang,
        timeout=args.timeout,
        retries=args.retries,
        proxy=args.proxy,
        use_env_proxy=args.use_env_proxy,
        screenshot_timeout=args.screenshot_timeout,
        width=args.width,
        height=args.height,
        browser_channel=args.browser_channel,
        keep_html=args.keep_html or bool(args.html_output),
    )
    result = await service.create_report(args.uid, force=args.force)
    if args.output and result.image_path != args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.image_path.replace(args.output)
        return args.output
    return result.image_path


def main() -> int:
    try:
        output = asyncio.run(run())
        print(f"报告图片已生成：{output.resolve()}")
        return 0
    except Exception as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
