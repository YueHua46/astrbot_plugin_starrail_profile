# hk-star-rail-profile

把 MiHoMo Parsed Data API 的星穹铁道展示柜数据渲染为二次元风格 HTML，并可按 UID 生成 1080x1920 报告图片。

## 生成报告图

```powershell
.venv\Scripts\python.exe generate_report.py 100534214
```

默认输出到：

```text
reports/starrail_report_100534214.png
```

常用参数：

```powershell
# 指定语言
.venv\Scripts\python.exe generate_report.py 100534214 --lang cn

# 强制刷新接口缓存
.venv\Scripts\python.exe generate_report.py 100534214 --force

# 指定输出图片
.venv\Scripts\python.exe generate_report.py 100534214 -o reports\my_report.png

# 保留中间 HTML，方便调样式
.venv\Scripts\python.exe generate_report.py 100534214 --keep-html

# 从已有 JSON 文件生成，不请求接口
.venv\Scripts\python.exe generate_report.py --json data.json -o reports\from_json.png

# 网络需要代理时
.venv\Scripts\python.exe generate_report.py 100534214 --proxy http://127.0.0.1:7890
```

脚本会自动寻找本机 Chrome 或 Edge，并用 headless 截图。如果找不到浏览器，可以用 `--chrome-path` 指定可执行文件路径。

## 交互 HTML

`index.html` 是可交互展示页，可以直接用本地静态服务打开：

```powershell
python -m http.server 8010 --bind 127.0.0.1
```

然后访问 `http://127.0.0.1:8010/index.html`。
