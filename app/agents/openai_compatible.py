from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx


LOCAL_HTTP_HOSTS = {"localhost", "127.0.0.1", "::1"}


def normalize_base_url(base_url: str) -> str:
    return str(base_url or "").strip().rstrip("/")


def validate_openai_compatible_base_url(base_url: str) -> str:
    raw = normalize_base_url(base_url)
    if not raw:
        raise ValueError("base_url is required")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base_url must use http or https")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("base_url host is missing")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_link_local or ip.is_multicast):
        raise ValueError("http base_url is only allowed for localhost")
    if parsed.scheme == "http" and host not in LOCAL_HTTP_HOSTS:
        raise ValueError("http base_url is only allowed for localhost")
    return raw


def request_json(method: str, url: str, **kwargs: Any) -> httpx.Response:
    timeout = kwargs.pop("timeout", 30.0)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        return client.request(method, url, **kwargs)


def _auth_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _redact(text: str, api_key: str) -> str:
    if api_key and api_key in text:
        return text.replace(api_key, "[redacted]")
    return text


def chat_completions(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    timeout_s: float,
) -> str:
    base = validate_openai_compatible_base_url(base_url)
    response = request_json(
        "POST",
        f"{base}/chat/completions",
        headers=_auth_headers(api_key),
        json={"model": model, "messages": messages},
        timeout=timeout_s,
    )
    try:
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(_redact(str(exc), api_key)) from exc
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI-compatible chat returned no choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI-compatible chat returned an empty answer.")
    return content.strip()


def healthcheck(
    base_url: str,
    api_key: str,
    model: str = "",
    timeout_s: float = 8.0,
) -> tuple[str, str]:
    try:
        base = validate_openai_compatible_base_url(base_url)
    except ValueError as exc:
        return "failed", str(exc)
    try:
        response = request_json(
            "GET",
            f"{base}/models",
            headers=_auth_headers(api_key),
            timeout=timeout_s,
        )
        if response.status_code == 200:
            return "ok", "models endpoint responded"
        return "failed", _redact(f"models endpoint returned HTTP {response.status_code}", api_key)
    except Exception as exc:
        return "failed", _redact(str(exc), api_key)
