"""Baidu general object and scene recognition API adapter."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from time import monotonic

import httpx


@dataclass(frozen=True, slots=True)
class Detection:
    name: str
    confidence: float


class VisionApiError(RuntimeError):
    def __init__(self, code: str, provider_message: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.provider_message = provider_message

    @property
    def user_message(self) -> str:
        known = {
            "6": "当前应用没有果蔬识别接口权限。",
            "17": "果蔬识别调用额度已用完。",
            "18": "果蔬识别请求过于频繁。",
            "216201": "百度无法解析这张图片。",
            "216202": "图片尺寸不符合百度接口要求。",
        }
        return known.get(self.code, "百度果蔬识别服务拒绝了本次请求。")


class VisionApiClient:
    TOKEN_ENDPOINT = "https://aip.baidubce.com/oauth/2.0/token"

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        secret_key: str,
        timeout: float = 20,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def _get_access_token(self) -> str:
        if self._access_token and monotonic() < self._token_expires_at:
            return self._access_token

        response = httpx.post(
            self.TOKEN_ENDPOINT,
            params={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise VisionApiError(
                str(payload.get("error", "TOKEN_FAILED")),
                str(payload.get("error_description", "")),
            )
        self._access_token = str(token)
        expires_in = int(payload.get("expires_in", 2_592_000))
        self._token_expires_at = monotonic() + max(60, expires_in - 60)
        return self._access_token

    def recognize(self, image_bytes: bytes) -> list[Detection]:
        token = self._get_access_token()
        response = httpx.post(
            self.endpoint,
            params={"access_token": token},
            data={
                "image": base64.b64encode(image_bytes).decode("ascii"),
                "top_num": 5,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if "error_code" in payload:
            raise VisionApiError(
                str(payload["error_code"]),
                str(payload.get("error_msg", "")),
            )
        return [
            Detection(name=str(item["name"]), confidence=float(item["score"]))
            for item in payload.get("result", [])
            if "name" in item and "score" in item
        ]
