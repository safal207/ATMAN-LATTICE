from __future__ import annotations

import json
import os
import sys

from model.runtime_calibration import CALIBRATION_PROTOCOL, execute_calibration_request
from model.runtime_worker import _server_enforcement


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("calibration request must be a JSON object")
        if request.get("protocol") != CALIBRATION_PROTOCOL:
            raise ValueError("unsupported calibration protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-CALIBRATION/1.12 requires ATMAN_RUNTIME_DB")
        response = execute_calibration_request(
            request,
            enforcement=_server_enforcement(),
            db_path=db_path,
        )
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {
            "protocol": CALIBRATION_PROTOCOL,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
