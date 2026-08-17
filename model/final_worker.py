from __future__ import annotations

import json
import os
import sys

from model.runtime_protected_holdout import FINAL_PROTOCOL, execute_protected_holdout_request
from model.runtime_worker import _server_enforcement


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("protected final holdout request must be a JSON object")
        if request.get("protocol") != FINAL_PROTOCOL:
            raise ValueError("unsupported protected final holdout protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-FINAL/1.17 requires ATMAN_RUNTIME_DB")
        response = execute_protected_holdout_request(request, enforcement=_server_enforcement(), db_path=db_path)
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {"protocol": FINAL_PROTOCOL, "ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
