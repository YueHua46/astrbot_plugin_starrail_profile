# astrbot_plugin_starrail_profile

根据星穹铁道 UID 生成二次元风格展示柜 Profile 图片的 AstrBot 插件。支持指令触发、自然语言触发和 LLM 工具调用。

## 功能

- 通过 MiHoMo Parsed Data API 查询星穹铁道公开展示柜。
- 生成 1080x1920 竖版 Profile 图片卡片。
- 请求失败后最多自动重试 5 次。
- 使用 Playwright 渲染 HTML 并截图，适合 Linux 服务器托管。

## 安装

把本仓库放到 AstrBot 的插件目录后安装依赖：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Linux 如果缺少浏览器系统依赖，可以执行：

```bash
python -m playwright install --with-deps chromium
```

## 使用

```text
/srprofile 100534214
/sr 100534214
```

也可以自然语言触发：

```text
帮我查一下星铁 UID 100534214
```

如果 AstrBot 启用了 LLM 工具调用，模型也可以调用 `query_starrail_profile` 工具生成图片。

## 配置

插件支持在 AstrBot 后台配置：

- `lang`: API 语言，默认 `cn`
- `timeout`: API 请求超时秒数，默认 `30`
- `retries`: 请求失败后的最大重试次数，默认 `5`
- `proxy`: 可选代理，例如 `http://127.0.0.1:7890`
- `output_dir`: 报告图片输出目录
- `screenshot_timeout`: Playwright 截图超时秒数
- `browser_channel`: 可选浏览器通道，例如 `chrome`、`msedge`

## 本地调试

```powershell
uv sync
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe generate_report.py 100534214 --browser-channel chrome
```

如果已经安装 Playwright Chromium，可以省略 `--browser-channel chrome`。
