# astrbot_plugin_starrail_profile

星穹铁道 UID 展示柜 Profile 图片生成插件。项目结构对齐 AstrBot 官方插件模板，核心文件保持扁平：

```text
main.py
metadata.yaml
_conf_schema.json
requirements.txt
README.md
```

## 功能

- 通过 MiHoMo Parsed Data API 查询星穹铁道公开展示柜。
- 生成 1080x1920 二次元风格 Profile 图片。
- 支持指令触发和自然语言触发。
- 请求失败后最多自动重试 5 次。
- 使用 Playwright 渲染图片，适合 Linux 服务器部署。

## 安装

在 AstrBot 插件市场或插件仓库安装：

```text
https://github.com/YueHua46/astrbot_plugin_starrail_profile
```

依赖：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Linux 部署如果缺浏览器系统依赖：

```bash
python -m playwright install --with-deps chromium
```

## 使用

```text
/srprofile 100534214
/sr 100534214
```

自然语言也可以触发：

```text
帮我查一下星铁 UID 100534214
```

## 配置

- `lang`: API 语言，默认 `cn`
- `timeout`: API 请求超时秒数，默认 `30`
- `retries`: 请求失败后的最大重试次数，默认 `5`
- `proxy`: 可选代理，例如 `http://127.0.0.1:7890`
- `use_env_proxy`: 是否使用系统环境代理
- `asset_base`: 素材镜像基础地址，默认 jsDelivr，并内置其他镜像兜底
- `asset_timeout`: 单个素材下载超时秒数，默认 `20`
- `inline_assets`: 是否将远程素材内嵌进 HTML，默认开启，建议开启以避免截图时头像/角色图空白
- `output_dir`: 报告图片输出目录
- `screenshot_timeout`: Playwright 截图超时秒数
- `browser_channel`: 可选浏览器通道，例如 `chrome`、`msedge`
- `keep_html`: 是否保留中间 HTML
