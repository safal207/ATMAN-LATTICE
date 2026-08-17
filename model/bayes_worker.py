from __future__ import annotations

import json
import os
import sys

from model.runtime_active_verification import make_active_policy_from_env
from model.runtime_bayesian import BAYES_PROTOCOL, execute_bayesian_request
from model.runtime_economy import make_economy_policy_from_env
from model.runtime_worker import _server_enforcement


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("Bayesian request must be a JSON object")
        if request.get("protocol") != BAYES_PROTOCOL:
            raise ValueError("unsupported Bayesian evidence protocol")
        db_path = os.environ.get("ATMAN_RUNTIME_DB")
        if not db_path:
            raise ValueError("ATMAN-BAYES/1.10 requires ATMAN_RUNTIME_DB")
        response = execute_bayesian_request(
            request,
            enforcement=_server_enforcement(),
            db_path=db_path,
            economy_policy=make_economy_policy_from_env(),
            active_policy=make_active_policy_from_env(),
        )
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {
            "protocol": BAYES_PROTOCOL,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
