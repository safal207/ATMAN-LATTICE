from __future__ import annotations

import json
import os
import sys

from model.runtime_remediation import REMEDIATION_PROTOCOL, execute_remediation_request
from model.runtime_worker import _server_enforcement


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("remediation request must be a JSON object")
        if request.get("protocol") != REMEDIATION_PROTOCOL:
            raise ValueError("unsupported remediation protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-REMEDIATE/1.19 requires ATMAN_RUNTIME_DB")
        response = execute_remediation_request(request, enforcement=_server_enforcement(), db_path=db_path)
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {"protocol": REMEDIATION_PROTOCOL, "ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
