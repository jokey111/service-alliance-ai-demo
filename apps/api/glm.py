"""Zhipu standard API adapter. Coding Plan keys are not used for the public demo."""
from __future__ import annotations

import os
import time
from collections import deque

import httpx


API_KEY = os.getenv("ZHIPU_API_KEY", "")
BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
CHAT_MODEL = os.getenv("ZHIPU_CHAT_MODEL", "glm-5.3-flash")
CHAT_MODELS = ("glm-5.3-flash", "glm-5.3-flashx", "glm-5.3")
MAX_CALLS_PER_MINUTE = max(1, int(os.getenv("ZHIPU_MAX_CALLS_PER_MINUTE", "12")))
MAX_CALLS_PER_DAY = max(1, int(os.getenv("ZHIPU_MAX_CALLS_PER_DAY", "100")))
CALL_TIMES: deque[float] = deque()
DAY_CALL_TIMES: deque[float] = deque()


def configured() -> bool:
    return bool(API_KEY)


async def completion(messages: list[dict], *, max_tokens: int = 600, model: str | None = None) -> str | None:
    """Generate short user-facing text. Never infer business facts absent from messages."""
    if not configured():
        return None
    current = time.monotonic()
    while CALL_TIMES and CALL_TIMES[0] <= current - 60:
        CALL_TIMES.popleft()
    while DAY_CALL_TIMES and DAY_CALL_TIMES[0] <= current - 86400:
        DAY_CALL_TIMES.popleft()
    if len(CALL_TIMES) >= MAX_CALLS_PER_MINUTE or len(DAY_CALL_TIMES) >= MAX_CALLS_PER_DAY:
        return None
    CALL_TIMES.append(current)
    DAY_CALL_TIMES.append(current)
    payload = {
        "model": model or CHAT_MODEL,
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
