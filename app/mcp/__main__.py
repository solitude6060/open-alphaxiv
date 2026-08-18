from __future__ import annotations

import json
import sys

from app.main import service
from app.mcp.server import handle_mcp_request


def main() -> None:
    paper_service = service()
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        body = json.loads(raw)
        response = handle_mcp_request(body, paper_service)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
