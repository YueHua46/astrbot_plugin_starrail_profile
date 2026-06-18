import base64
from pathlib import Path


class PlaywrightRenderer:
    def __init__(
        self,
        width: int = 1080,
        height: int = 1920,
        timeout: int = 120,
        browser_channel: str | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.timeout_ms = timeout * 1000
        self.browser_channel = browser_channel or None

    async def screenshot_html(self, html_path: Path, output_path: Path) -> Path:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("缺少 playwright 依赖，请先安装：pip install playwright") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)

            page = await browser.new_page(
                viewport={"width": self.width, "height": self.height},
                device_scale_factor=1,
            )
            page.set_default_timeout(self.timeout_ms)
            page.set_default_navigation_timeout(self.timeout_ms)
            try:
                await page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 10000))
                except Exception:
                    pass
                await page.evaluate(
                    """
                    async (timeout) => {
                      const imageUrls = Array.from(document.images).map((img) => img.currentSrc || img.src);
                      const backgroundUrls = Array.from(document.querySelectorAll("*")).flatMap((el) => {
                        const bg = getComputedStyle(el).backgroundImage || "";
                        return Array.from(bg.matchAll(/url\\(["']?([^"')]+)["']?\\)/g)).map((match) => match[1]);
                      });
                      const urls = Array.from(new Set([...imageUrls, ...backgroundUrls].filter(Boolean)));
                      const waitImageUrl = (url) => new Promise((resolve) => {
                        const img = new Image();
                        img.onload = resolve;
                        img.onerror = resolve;
                        img.src = url;
                        if (img.complete) resolve();
                      });
                      const waitDomImages = Promise.all(Array.from(document.images).map((img) => {
                        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                        return new Promise((resolve) => {
                          img.onload = resolve;
                          img.onerror = resolve;
                        });
                      }));
                      const waitUrls = Promise.all(urls.map(waitImageUrl));
                      const waitTimeout = new Promise((resolve) => setTimeout(resolve, timeout));
                      await Promise.race([Promise.all([waitDomImages, waitUrls]), waitTimeout]);
                      document.querySelectorAll("img[data-fallback]").forEach((img) => {
                        if (!img.complete || img.naturalWidth === 0) {
                          img.src = img.dataset.fallback;
                        }
                      });
                      await Promise.race([
                        Promise.all(Array.from(document.images).map((img) => {
                          if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                          return new Promise((resolve) => {
                            img.onload = resolve;
                            img.onerror = resolve;
                          });
                        })),
                        new Promise((resolve) => setTimeout(resolve, Math.min(timeout, 8000)))
                      ]);
                    }
                    """,
                    min(self.timeout_ms, 15000),
                )
                await page.wait_for_timeout(800)
                session = await page.context.new_cdp_session(page)
                screenshot = await session.send(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "clip": {
                            "x": 0,
                            "y": 0,
                            "width": self.width,
                            "height": self.height,
                            "scale": 1,
                        },
                        "captureBeyondViewport": False,
                    },
                )
                output_path.write_bytes(base64.b64decode(screenshot["data"]))
            finally:
                await browser.close()

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Playwright 没有生成有效 PNG 文件。")
        return output_path

    async def _launch_browser(self, playwright):
        if self.browser_channel:
            return await playwright.chromium.launch(headless=True, channel=self.browser_channel)

        try:
            return await playwright.chromium.launch(headless=True)
        except Exception as first_error:
            for channel in ("chrome", "msedge"):
                try:
                    return await playwright.chromium.launch(headless=True, channel=channel)
                except Exception:
                    continue
            raise RuntimeError(
                "Playwright Chromium 启动失败，请在部署环境执行：python -m playwright install chromium"
            ) from first_error
