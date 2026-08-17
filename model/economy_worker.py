from __future__ import annotations

import json
import os
import sys

from model.runtime_economy import (
    ECONOMY_PROTOCOL,
    execute_economy_request,
    make_economy_policy_from_env,
)
from model.runtime_worker import _server_enforcement


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("economy request must be a JSON object")
        if request.get("protocol") != ECONOMY_PROTOCOL:
            raise ValueError("unsupported economy protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-ECONOMY/1.8 requires ATMAN_RUNTIME_DB")
        response = execute_economy_request(
            request,
            enforcement=_server_enforcement(),
            db_path=db_path,
            policy=make_economy_policy_from_env(),
        )
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {
            "protocol": ECONOMY_PROTOCOL,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
