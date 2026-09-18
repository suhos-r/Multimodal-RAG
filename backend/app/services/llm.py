"""LLM via local Ollama OpenAI-compatible endpoint. Mock hook for tests."""
import json
import time

import httpx

from ..config import settings

_MOCK = None


def set_mock(fn) -> None:
    """Tests: fn(messages) -> str (full text) or list[str] (stream deltas)."""
    global _MOCK
    _MOCK = fn


def _url() -> str:
    return f"{settings.OLLAMA_BASE_URL}/v1/chat/completions"


async def acomplete(messages: list[dict], temperature: float = 0.1, max_tokens: int = 800) -> dict:
    if _MOCK is not None:
        out = _MOCK(messages)
        text = "".join(out) if isinstance(out, list) else out
        return {"text": text, "model": settings.LLM_MODEL, "ms": 0, "mock": True}
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(_url(), json={"model": settings.LLM_MODEL, "messages": messages,
                                            "temperature": temperature, "max_tokens": max_tokens, "stream": False})
        r.raise_for_status()
        data = r.json()
    return {"text": data["choices"][0]["message"]["content"], "model": settings.LLM_MODEL,
            "ms": int((time.perf_counter() - t0) * 1000), "mock": False}


async def astream(messages: list[dict], temperature: float = 0.1, max_tokens: int = 800):
    """Yields text deltas."""
    if _MOCK is not None:
        out = _MOCK(messages)
        for d in (out if isinstance(out, list) else [out]):
            yield d
        return
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", _url(), json={
                "model": settings.LLM_MODEL, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens, "stream": True}) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
                except Exception:
                    continue
                if delta:
                    yield delta
