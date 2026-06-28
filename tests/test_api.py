from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.main import create_app


def endpoint(path: str) -> Callable[..., Any]:
    app = create_app()
    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"route not found: {path}")


def test_root_endpoint_points_to_api_entrypoints() -> None:
    payload = endpoint("/")()

    assert payload["status"] == "ok"
    assert payload["api_health_url"] == "/api/health"
    assert payload["api_docs_url"] == "/docs"


def test_codex_status_describes_local_connector_boundary() -> None:
    payload = endpoint("/api/codex/status")()

    assert payload["status"] in {"ready", "not_configured"}
    assert "chatgpt_login" in payload["auth_modes"]
    assert "generic browser OAuth" in payload["integration_boundary"]
    assert "codex_access_token_present" in payload
