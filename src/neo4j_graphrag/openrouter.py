from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    app_name: str = os.getenv("OPENROUTER_APP_NAME", "Neo4j GraphRAG")
    http_referer: str = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost")
    chat_model: str = os.getenv("OPENROUTER_CHAT_MODEL", "openai/gpt-4o-mini")
    embedding_model: str = os.getenv("OPENROUTER_EMBEDDING_MODEL", "")


def enabled(config: OpenRouterConfig | None = None) -> bool:
    config = config or OpenRouterConfig()
    return bool(config.api_key)


def _request(path: str, payload: dict[str, Any], config: OpenRouterConfig | None = None) -> dict[str, Any]:
    config = config or OpenRouterConfig()
    if not config.api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{config.base_url}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": config.http_referer,
            "X-Title": config.app_name,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenRouter request failed: {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc


def chat(messages: list[dict[str, str]], model: str | None = None, temperature: float = 0.2) -> str:
    config = OpenRouterConfig()
    payload = {
        "model": model or config.chat_model,
        "messages": messages,
        "temperature": temperature,
    }
    response = _request("/chat/completions", payload, config=config)
    return response["choices"][0]["message"]["content"]


def embeddings(texts: list[str], model: str | None = None) -> list[list[float]]:
    config = OpenRouterConfig()
    embedding_model = model or config.embedding_model
    if not embedding_model:
        raise RuntimeError("OPENROUTER_EMBEDDING_MODEL is not configured")
    payload = {
        "model": embedding_model,
        "input": texts,
    }
    response = _request("/embeddings", payload, config=config)
    return [item["embedding"] for item in response["data"]]
