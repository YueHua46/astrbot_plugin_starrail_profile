import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import requests


API_BASE = "https://api.mihomo.me/sr_info_parsed"
ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "report_template.html"
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
        "is_display": True,
        "space_info": {
            "memory_data": {"level": 21, "chaos_id": 1014, "chaos_level": 11, "chaos_star_count": 33},
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
            "path": {"id": "Warrior", "name": "毁灭", "icon": "icon/path/Destruction.png"},
            "element": {"id": "Ice", "name": "冰", "color": "#47C7FD", "icon": "icon/element/Ice.png"},
            "light_cone": {
                "id": "23014",
                "name": "此身为剑",
                "rarity": 5,
                "rank": 1,
                "level": 80,
                "promotion": 6,
                "icon": "icon/light_cone/23014.png",
            },
            "attributes": [
                {"field": "hp", "name": "生命值", "display": "3250"},
                {"field": "atk", "name": "攻击力", "display": "2542"},
                {"field": "spd", "name": "速度", "display": "134"},
                {"field": "crit_rate", "name": "暴击率", "display": "48.5%"},
                {"field": "crit_dmg", "name": "暴击伤害", "display": "210.4%"},
                {"field": "break_dmg", "name": "击破特攻", "display": "-"},
            ],
            "pos": [0],
        },
        {
            "id": "1301",
            "name": "阮·梅",
            "rarity": 5,
            "rank": 1,
            "level": 80,
            "promotion": 6,
            "icon": "icon/character/1301.png",
            "preview": "image/character_preview/1301.png",
            "portrait": "image/character_portrait/1301.png",
            "path": {"id": "Harmony", "name": "同谐", "icon": "icon/path/Harmony.png"},
            "element": {"id": "Ice", "name": "冰", "color": "#47C7FD", "icon": "icon/element/Ice.png"},
            "light_cone": {
                "id": "23024",
                "name": "镜中故我",
                "rarity": 5,
                "rank": 1,
                "level": 80,
                "promotion": 6,
                "icon": "icon/light_cone/23024.png",
            },
            "attributes": [
                {"field": "hp", "name": "生命值", "display": "3988"},
                {"field": "atk", "name": "攻击力", "display": "1810"},
                {"field": "spd", "name": "速度", "display": "161"},
                {"field": "crit_rate", "name": "暴击率", "display": "-"},
                {"field": "crit_dmg", "name": "暴击伤害", "display": "-"},
                {"field": "break_dmg", "name": "击破特攻", "display": "183.2%"},
            ],
            "pos": [1],
        },
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据星穹铁道 UID 生成 1080x1920 报告 PNG。")
    parser.add_argument("uid", nargs="?", help="星穹铁道 UID，例如 100534214。使用 --demo 或 --json 时可省略。")
    parser.add_argument("--lang", default="cn", help="接口语言，默认 cn。")
    parser.add_argument("--output", "-o", type=Path, help="输出 PNG 路径，默认 reports/starrail_report_<uid>.png。")
    parser.add_argument("--json", type=Path, help="从本地 sr_info_parsed JSON 文件生成图片，不请求接口。")
    parser.add_argument("--demo", action="store_true", help="使用内置示例数据生成图片。")
    parser.add_argument("--force", action="store_true", help="请求接口时强制刷新缓存。")
    parser.add_argument("--proxy", help="请求接口使用的代理，例如 http://127.0.0.1:7890。")
    parser.add_argument("--use-env-proxy", action="store_true", help="允许 requests 使用系统环境代理。默认关闭。")
    parser.add_argument("--chrome-path", type=Path, help="Chrome 或 Edge 可执行文件路径。")
    parser.add_argument("--keep-html", action="store_true", help="保留渲染用 HTML 文件。")
    parser.add_argument("--html-output", type=Path, help="指定保留的 HTML 文件路径。")
    parser.add_argument("--width", type=int, default=1080, help="截图宽度，默认 1080。")
    parser.add_argument("--height", type=int, default=1920, help="截图高度，默认 1920。")
    parser.add_argument("--timeout", type=int, default=30, help="接口请求超时秒数，默认 30。")
    return parser.parse_args()


def fetch_profile(uid: str, lang: str, force: bool, timeout: int, proxy: str | None, use_env_proxy: bool) -> dict:
    params = {"lang": lang}
    if force:
        params["is_force_update"] = "true"

    session = requests.Session()
    session.trust_env = use_env_proxy
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    response = session.get(
        f"{API_BASE}/{uid}",
        params=params,
        timeout=timeout,
        headers={"Accept": "application/json", "User-Agent": "hk-star-rail-report/1.0"},
    )
    response.raise_for_status()
    data = response.json()
    if "player" not in data:
        raise ValueError("接口响应里没有 player 字段，可能 UID 不存在或数据格式变化。")
    return data


def load_data(args: argparse.Namespace) -> tuple[dict, str]:
    if args.demo:
      return DEMO_DATA, "demo"
    if args.json:
        return json.loads(args.json.read_text(encoding="utf-8")), args.json.stem
    if not args.uid:
        raise ValueError("请传入 uid，或使用 --demo / --json。")
    return fetch_profile(args.uid, args.lang, args.force, args.timeout, args.proxy, args.use_env_proxy), args.uid


def find_browser(explicit: Path | None) -> Path:
    if explicit:
        if explicit.exists():
            return explicit
        raise FileNotFoundError(f"找不到浏览器：{explicit}")

    names = ["chrome", "chrome.exe", "msedge", "msedge.exe"]
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)

    candidates = [
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/microsoft-edge"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("找不到 Chrome/Edge。请安装 Chrome，或用 --chrome-path 指定路径。")


def build_html(data: dict, html_path: Path) -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = template.replace("__REPORT_DATA__", payload).replace("__GENERATED_AT__", generated_at)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")


def screenshot(browser: Path, html_path: Path, output_path: Path, width: int, height: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix="starrail-chrome-"))
    command = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        "--force-device-scale-factor=1",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=7000",
        f"--screenshot={output_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Chrome 截图失败。\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Chrome 没有生成有效 PNG 文件。")


def main() -> int:
    args = parse_args()
    try:
        data, name = load_data(args)
        uid = data.get("player", {}).get("uid") or name
        output = args.output or REPORT_DIR / f"starrail_report_{uid}.png"
        html_output = args.html_output or REPORT_DIR / f"starrail_report_{uid}.html"
        temp_html = html_output if (args.keep_html or args.html_output) else Path(tempfile.gettempdir()) / f"starrail_report_{uid}.html"

        build_html(data, temp_html)
        browser = find_browser(args.chrome_path)
        screenshot(browser, temp_html, output, args.width, args.height)

        if not args.keep_html and not args.html_output:
            temp_html.unlink(missing_ok=True)

        print(f"报告图片已生成：{output.resolve()}")
        if args.keep_html or args.html_output:
            print(f"报告 HTML 已保留：{temp_html.resolve()}")
        return 0
    except Exception as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
