from __future__ import annotations

import json
import os
import sys

from model.runtime_verification import (
    VERIFY_PROTOCOL,
    execute_verification_request,
    make_capacity_policy_from_env,
)
from model.runtime_worker import _server_enforcement
from model.verification_keeper import (
    FINALIZE_OPERATION,
    decision_state_hash,
    execute_finalization_request,
)


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("verification request must be a JSON object")
        if request.get("protocol") != VERIFY_PROTOCOL:
            raise ValueError("unsupported verification protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-VERIFY/1.7 requires ATMAN_RUNTIME_DB")
        enforcement = _server_enforcement()
        if request.get("operation") == FINALIZE_OPERATION:
            response = execute_finalization_request(
                request,
                enforcement=enforcement,
                db_path=db_path,
            )
        else:
            response = execute_verification_request(
                request,
                enforcement=enforcement,
                db_path=db_path,
                policy=make_capacity_policy_from_env(),
            )
            if request.get("operation") == "evaluate_geometric_verification" and response.get("ok") is True:
                response["decision_state_hash"] = decision_state_hash(response["decision"])
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {
            "protocol": VERIFY_PROTOCOL,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
