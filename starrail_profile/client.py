import time
from dataclasses import dataclass
from typing import Any

import requests


API_BASE = "https://api.mihomo.me/sr_info_parsed"
RETRYABLE_STATUS = {408, 409, 425, 429}


@dataclass(slots=True)
class StarRailClient:
    lang: str = "cn"
    timeout: int = 30
    retries: int = 5
    proxy: str | None = None
    use_env_proxy: bool = False

    def fetch_profile(self, uid: str, force: bool = False) -> dict[str, Any]:
        params: dict[str, str] = {"lang": self.lang}
        if force:
            params["is_force_update"] = "true"

        session = requests.Session()
        session.trust_env = self.use_env_proxy
        if self.proxy:
            session.proxies = {"http": self.proxy, "https": self.proxy}

        max_retries = max(0, min(int(self.retries), 5))
        last_error: Exception | None = None
        headers = {"Accept": "application/json", "User-Agent": "astrbot-plugin-starrail-profile/1.0"}

        for attempt in range(max_retries + 1):
            try:
                response = session.get(
                    f"{API_BASE}/{uid}",
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
                if response.status_code >= 400:
                    if self._retryable_status(response.status_code) and attempt < max_retries:
                        raise requests.HTTPError(f"接口返回 {response.status_code}", response=response)
                    response.raise_for_status()

                data = response.json()
                if "player" not in data:
                    raise ValueError("接口响应里没有 player 字段，可能 UID 不存在或数据格式变化。")
                return data
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    if not self._retryable_status(exc.response.status_code):
                        break
                if attempt >= max_retries:
                    break
                time.sleep(self._retry_delay(attempt + 1))

        raise RuntimeError(f"请求失败，已重试 {max_retries} 次：{last_error}")

    @staticmethod
    def _retryable_status(status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS or 500 <= status_code <= 599

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return min(1.5 * (2 ** (attempt - 1)), 12)
