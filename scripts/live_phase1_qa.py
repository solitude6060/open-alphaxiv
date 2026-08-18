#!/usr/bin/env python3
"""Live paper Q&A through official CLIs. No browser OAuth. Writes JSON to stdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.main import claude_options, codex_options, opencode_options
from app.mcp.server import handle_mcp_request
from app.services import PaperService
from app.store import Store


def minimal_pdf_bytes() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj + b"\n")
        content.extend(b"endobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(content)


def _preview(text: str) -> str:
    return " ".join((text or "").split())[:240]


def _ask(service: PaperService, paper_id: int, mode: str, options: dict) -> dict[str, object]:
    kwargs = {
        "codex": {"codex_options": options},
        "claude_cli": {"claude_options": options},
        "opencode": {"opencode_options": options},
    }[mode]
    try:
        result = service.ask(
            paper_id,
            "In one short sentence, what is this document about?",
            answer_mode=mode,
            **kwargs,
        )
        return {
            "ok": True,
            "provider": result.get("retrieval", {}).get("provider"),
            "answer_preview": _preview(str(result.get("answer") or "")),
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "provider": mode, "answer_preview": "", "error": str(exc)[:400]}


def main() -> int:
    dest = (ROOT / "data" / "live-qa").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    service = PaperService(Store(dest / "live.db"), dest)
    paper = service.ingest_uploaded_pdf("live-qa.pdf", minimal_pdf_bytes(), title="Live QA fixture")
    settings = get_settings()
    rows = {
        "settings": {
            "codex_enabled": settings.codex_enabled,
            "claude_enabled": settings.claude_enabled,
            "opencode_enabled": settings.opencode_enabled,
        },
        "paper_id": paper["id"],
        "mcp_tools": [
            tool["name"]
            for tool in (handle_mcp_request(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                service,
            ) or {}).get("result", {}).get("tools", [])
        ],
        "codex": _ask(service, paper["id"], "codex", {**codex_options(), "timeout_seconds": 90}),
        "claude_cli": _ask(service, paper["id"], "claude_cli", {**claude_options(), "timeout_seconds": 90}),
        "opencode": _ask(service, paper["id"], "opencode", {**opencode_options(), "timeout_seconds": 90}),
    }
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if rows["codex"]["ok"] or rows["claude_cli"]["ok"] or rows["opencode"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
