"""Zhipu standard API adapter. Coding Plan keys are not used for the public demo."""
from __future__ import annotations

import os

import httpx


API_KEY = os.getenv("ZHIPU_API_KEY", "")
BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
CHAT_MODEL = os.getenv("ZHIPU_CHAT_MODEL", "glm-5.3-flash")


def configured() -> bool:
    return bool(API_KEY)


async def completion(messages: list[dict], *, max_tokens: int = 600) -> str | None:
    """Generate short user-facing text. Never infer business facts absent from messages."""
    if not configured():
        return None
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    return body["choices"][0]["message"].get("content")
