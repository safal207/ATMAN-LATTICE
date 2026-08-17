from __future__ import annotations

import json
import os
import sys

from model.runtime_revision import REVISION_PROTOCOL, execute_revision_request
from model.runtime_worker import _server_enforcement


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("model revision request must be a JSON object")
        if request.get("protocol") != REVISION_PROTOCOL:
            raise ValueError("unsupported model revision protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-REVISION/1.13 requires ATMAN_RUNTIME_DB")
        response = execute_revision_request(
            request,
            enforcement=_server_enforcement(),
            db_path=db_path,
        )
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {
            "protocol": REVISION_PROTOCOL,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
