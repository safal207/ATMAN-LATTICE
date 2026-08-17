from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import os
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import completion_from_dict, verification_scope, work_from_dict
from model.verification_economy import (
    CostObservationReceipt,
    EconomicVerificationCandidate,
    VerificationBudgetAllocationReceipt,
    VerificationEconomyPolicy,
    allocate_verification_budget,
    build_cost_estimator,
    make_economic_candidate,
    make_verification_economy_policy,
    record_cost_observation,
)

ECONOMY_PROTOCOL = "ATMAN-ECONOMY/1.8"
ECONOMY_OPERATIONS = {
    "submit_economic_candidate",
    "record_cost_observation",
    "preview_budget_allocation",
    "finalize_budget_allocation",
    "get_economy_state",
}

ROLE_ECONOMY_SUBMITTER = "VERIFICATION_ECONOMY_SUBMITTER"
ROLE_COST_METER = "VERIFICATION_COST_METER"
ROLE_BUDGET_KEEPER = "VERIFICATION_BUDGET_KEEPER"
GLOBAL_ECONOMY_SCOPE = "verification-economy:global"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def candidate_to_dict(candidate: EconomicVerificationCandidate) -> dict[str, object]:
    candidate.validate()
    return asdict(candidate)


def candidate_from_dict(data: Mapping[str, object]) -> EconomicVerificationCandidate:
    candidate = EconomicVerificationCandidate(
        work_hash=str(data["work_hash"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        estimator_key=str(data["estimator_key"]),
        declared_cost_units=int(data["declared_cost_units"]),
        value_units=int(data["value_units"]),
        risk_units=int(data["risk_units"]),
        priority=int(data["priority"]),
        submitted_at=int(data["submitted_at"]),
        candidate_hash=str(data["candidate_hash"]),
    )
    candidate.validate()
    return candidate


def observation_to_dict(observation: CostObservationReceipt) -> dict[str, object]:
    observation.validate()
    return asdict(observation)


def observation_from_dict(data: Mapping[str, object]) -> CostObservationReceipt:
    observation = CostObservationReceipt(
        work_hash=str(data["work_hash"]),
        completion_hash=str(data["completion_hash"]),
        estimator_key=str(data["estimator_key"]),
        observed_cost_units=int(data["observed_cost_units"]),
        measured_at=int(data["measured_at"]),
        meter_ref=str(data["meter_ref"]),
        observation_hash=str(data["observation_hash"]),
    )
    observation.validate()
    return observation


def allocation_to_dict(allocation: VerificationBudgetAllocationReceipt) -> dict[str, object]:
    allocation.validate()
    data = asdict(allocation)
    for key in (
        "candidate_hashes",
        "estimator_snapshot_hashes",
        "ranked_candidate_hashes",
        "funded_candidate_hashes",
        "deferred_budget_candidate_hashes",
        "deferred_oversized_candidate_hashes",
    ):
        data[key] = list(data[key])
    data["estimated_costs"] = [[key, value] for key, value in allocation.estimated_costs]
    return data


def make_economy_policy_from_env() -> VerificationEconomyPolicy:
    return make_verification_economy_policy(
        os.environ.get("ATMAN_ECONOMY_POLICY_REF", "atman:verification-economy:runtime:v1.8"),
        budget_units=int(os.environ.get("ATMAN_VERIFICATION_BUDGET_UNITS", "20")),
        max_funded_items=int(os.environ.get("ATMAN_VERIFICATION_BUDGET_MAX_ITEMS", "10")),
        bootstrap_cost_units=int(os.environ.get("ATMAN_VERIFICATION_BOOTSTRAP_COST", "10")),
        min_samples_for_confidence=int(os.environ.get("ATMAN_VERIFICATION_MIN_COST_SAMPLES", "3")),
        uncertainty_premium_units=int(os.environ.get("ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM", "2")),
        value_weight=int(os.environ.get("ATMAN_VERIFICATION_VALUE_WEIGHT", "1")),
        risk_weight=int(os.environ.get("ATMAN_VERIFICATION_RISK_WEIGHT", "2")),
        priority_weight=int(os.environ.get("ATMAN_VERIFICATION_PRIORITY_WEIGHT", "1")),
        aging_quantum=int(os.environ.get("ATMAN_VERIFICATION_ECONOMY_AGING_QUANTUM", "60")),
    )


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='verification_work'"
    ).fetchone()
    if exists is None:
        conn.close()
        raise ValueError("verification economy requires initialized v1.7 verification_work state")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_economy_candidate (
            work_hash TEXT PRIMARY KEY,
            candidate_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_cost_observation (
            work_hash TEXT PRIMARY KEY,
            observation_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_budget_allocation (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            generation INTEGER NOT NULL,
            state_hash TEXT NOT NULL,
            allocation_json TEXT NOT NULL
        )
        """
    )
    return conn


def _enforce(
    grant: AuthorityGrant,
    proof: AuthorityProof,
    *,
    action: object,
    required_role: str,
    required_scope: str,
    enforcement: EnforcementContext,
) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=enforcement.trusted_issuer_keys,
        current_policy_generation=enforcement.policy_generation,
        now=enforcement.now,
    )
    failures = list(limitations)
    if proof.role != required_role:
        failures.append("required_role_mismatch")
    if proof.scope != required_scope:
        failures.append("required_scope_mismatch")
    if not valid or failures:
        raise PermissionError("verification economy authority failed: " + ",".join(dict.fromkeys(failures)))


def _load_candidate_rows(conn: sqlite3.Connection, *, only_incomplete: bool) -> tuple[EconomicVerificationCandidate, ...]:
    where = "WHERE w.completion_json IS NULL" if only_incomplete else ""
    rows = conn.execute(
        f"""
        SELECT c.candidate_json
        FROM verification_economy_candidate c
        JOIN verification_work w ON w.work_hash = c.work_hash
        {where}
        ORDER BY c.work_hash
        """
    ).fetchall()
    return tuple(candidate_from_dict(json.loads(row[0])) for row in rows)


def _load_observations(conn: sqlite3.Connection) -> tuple[CostObservationReceipt, ...]:
    rows = conn.execute(
        "SELECT observation_json FROM verification_cost_observation ORDER BY work_hash"
    ).fetchall()
    return tuple(observation_from_dict(json.loads(row[0])) for row in rows)


def _current_economy_state(conn: sqlite3.Connection, policy: VerificationEconomyPolicy) -> dict[str, object]:
    candidates = _load_candidate_rows(conn, only_incomplete=True)
    observations = _load_observations(conn)
    estimator_keys = sorted({item.estimator_key for item in candidates} | {item.estimator_key for item in observations})
    estimators = {
        key: build_cost_estimator(key, observations)
        for key in estimator_keys
    }
    state_material = {
        "domain": "ATMAN-LATTICE/runtime-verification-economy-state/v1.8",
        "policy_hash": policy.policy_hash,
        "candidate_hashes": [item.candidate_hash for item in candidates],
        "estimator_snapshot_hashes": [estimators[key].snapshot_hash for key in sorted(estimators)],
    }
    return {
        "candidates": candidates,
        "estimators": estimators,
        "state_hash": _digest(state_material),
    }


def action_submit_candidate(candidate: EconomicVerificationCandidate) -> dict[str, object]:
    candidate.validate()
    return {
        "operation": "submit_economic_candidate",
        "candidate_hash": candidate.candidate_hash,
        "work_hash": candidate.work_hash,
        "subject_identity_ref": candidate.subject_identity_ref,
        "estimator_key": candidate.estimator_key,
        "value_units": candidate.value_units,
        "risk_units": candidate.risk_units,
        "priority": candidate.priority,
        "submitted_at": candidate.submitted_at,
    }


def action_record_cost(observation: CostObservationReceipt) -> dict[str, object]:
    observation.validate()
    return {
        "operation": "record_cost_observation",
        "observation_hash": observation.observation_hash,
        "work_hash": observation.work_hash,
        "completion_hash": observation.completion_hash,
        "estimator_key": observation.estimator_key,
        "observed_cost_units": observation.observed_cost_units,
        "measured_at": observation.measured_at,
        "meter_ref": observation.meter_ref,
    }


def action_finalize_allocation(
    *,
    state_hash: str,
    allocation_hash: str,
    policy_hash: str,
    generation: int,
    finalized_at: int,
) -> dict[str, object]:
    return {
        "operation": "finalize_budget_allocation",
        "state_hash": state_hash,
        "allocation_hash": allocation_hash,
        "policy_hash": policy_hash,
        "generation": generation,
        "finalized_at": finalized_at,
    }


def _submit_candidate(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> EconomicVerificationCandidate:
    work_hash = str(payload["work_hash"])
    row = conn.execute(
        "SELECT subject_identity_ref, work_json, completion_json FROM verification_work WHERE work_hash = ?",
        (work_hash,),
    ).fetchone()
    if row is None:
        raise ValueError("economic candidate must reference existing verification work")
    if row[2] is not None:
        raise ValueError("completed verification work cannot be newly funded")
    work = work_from_dict(json.loads(row[1]))
    candidate = make_economic_candidate(
        work_hash=work_hash,
        subject_identity_ref=str(row[0]),
        estimator_key=str(payload["estimator_key"]),
        declared_cost_units=work.cost_units,
        value_units=int(payload["value_units"]),
        risk_units=int(payload["risk_units"]),
        priority=int(payload.get("priority", work.priority)),
        submitted_at=work.submitted_at,
    )
    _enforce(
        grant,
        proof,
        action=action_submit_candidate(candidate),
        required_role=ROLE_ECONOMY_SUBMITTER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute(
        "SELECT candidate_json FROM verification_economy_candidate WHERE work_hash = ?",
        (work_hash,),
    ).fetchone()
    encoded = json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = candidate_from_dict(json.loads(existing[0]))
        if current != candidate:
            raise ValueError("work_hash already bound to different economic candidate")
        return current
    conn.execute(
        "INSERT INTO verification_economy_candidate(work_hash,candidate_json) VALUES(?,?)",
        (work_hash, encoded),
    )
    return candidate


def _record_observation(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> CostObservationReceipt:
    work_hash = str(payload["work_hash"])
    row = conn.execute(
        """
        SELECT w.completion_json, c.candidate_json
        FROM verification_work w
        JOIN verification_economy_candidate c ON c.work_hash = w.work_hash
        WHERE w.work_hash = ?
        """,
        (work_hash,),
    ).fetchone()
    if row is None:
        raise ValueError("cost observation requires an economic candidate")
    if row[0] is None:
        raise ValueError("cost observation requires completed verification work")
    completion = completion_from_dict(json.loads(row[0]))
    candidate = candidate_from_dict(json.loads(row[1]))
    observation = record_cost_observation(
        work_hash=work_hash,
        completion_hash=completion.completion_hash,
        estimator_key=candidate.estimator_key,
        observed_cost_units=int(payload["observed_cost_units"]),
        measured_at=enforcement.now,
        meter_ref=grant.subject_ref,
    )
    _enforce(
        grant,
        proof,
        action=action_record_cost(observation),
        required_role=ROLE_COST_METER,
        required_scope=GLOBAL_ECONOMY_SCOPE,
        enforcement=enforcement,
    )
    existing = conn.execute(
        "SELECT observation_json FROM verification_cost_observation WHERE work_hash = ?",
        (work_hash,),
    ).fetchone()
    encoded = json.dumps(observation_to_dict(observation), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = observation_from_dict(json.loads(existing[0]))
        if current != observation:
            raise ValueError("work_hash already has a different cost observation")
        return current
    conn.execute(
        "INSERT INTO verification_cost_observation(work_hash,observation_json) VALUES(?,?)",
        (work_hash, encoded),
    )
    return observation


def _preview(conn: sqlite3.Connection, policy: VerificationEconomyPolicy, *, measured_at: int) -> tuple[str, VerificationBudgetAllocationReceipt]:
    state = _current_economy_state(conn, policy)
    allocation = allocate_verification_budget(
        state["candidates"],
        state["estimators"],
        policy,
        measured_at=measured_at,
    )
    return str(state["state_hash"]), allocation


def _allocation_generation(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT generation FROM verification_budget_allocation WHERE singleton = 1"
    ).fetchone()
    return 0 if row is None else int(row[0])


def execute_economy_request(
    request: Mapping[str, object],
    *,
    enforcement: EnforcementContext,
    db_path: str,
    policy: VerificationEconomyPolicy,
) -> dict[str, object]:
    if request.get("protocol") != ECONOMY_PROTOCOL:
        raise ValueError("unsupported economy protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in ECONOMY_OPERATIONS:
        raise ValueError("unsupported economy operation")
    payload = _mapping(request.get("payload", {}), "payload")
    policy.validate()
    conn = _connect(db_path)
    try:
        if operation == "get_economy_state":
            state_hash, allocation = _preview(conn, policy, measured_at=enforcement.now)
            generation = _allocation_generation(conn)
            return {
                "protocol": ECONOMY_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "generation": generation,
                "state_hash": state_hash,
                "allocation": allocation_to_dict(allocation),
            }

        if operation == "preview_budget_allocation":
            state_hash, allocation = _preview(conn, policy, measured_at=enforcement.now)
            return {
                "protocol": ECONOMY_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "generation": _allocation_generation(conn),
                "state_hash": state_hash,
                "allocation": allocation_to_dict(allocation),
            }

        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")

        if operation == "submit_economic_candidate":
            candidate = _submit_candidate(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {
                "protocol": ECONOMY_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "candidate": candidate_to_dict(candidate),
            }

        if operation == "record_cost_observation":
            observation = _record_observation(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {
                "protocol": ECONOMY_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "observation": observation_to_dict(observation),
            }

        expected_state_hash = str(payload.get("expected_state_hash", ""))
        if not expected_state_hash:
            raise ValueError("expected_state_hash is required")
        state_hash, allocation = _preview(conn, policy, measured_at=enforcement.now)
        if state_hash != expected_state_hash:
            raise PermissionError("stale verification economy state")
        generation = _allocation_generation(conn) + 1
        action = action_finalize_allocation(
            state_hash=state_hash,
            allocation_hash=allocation.allocation_hash,
            policy_hash=policy.policy_hash,
            generation=generation,
            finalized_at=enforcement.now,
        )
        _enforce(
            grant,
            proof,
            action=action,
            required_role=ROLE_BUDGET_KEEPER,
            required_scope=GLOBAL_ECONOMY_SCOPE,
            enforcement=enforcement,
        )
        encoded = json.dumps(allocation_to_dict(allocation), sort_keys=True, separators=(",", ":"))
        conn.execute(
            """
            INSERT INTO verification_budget_allocation(singleton,generation,state_hash,allocation_json)
            VALUES(1,?,?,?)
            ON CONFLICT(singleton) DO UPDATE SET
                generation=excluded.generation,
                state_hash=excluded.state_hash,
                allocation_json=excluded.allocation_json
            """,
            (generation, state_hash, encoded),
        )
        conn.execute("COMMIT")
        return {
            "protocol": ECONOMY_PROTOCOL,
            "request_id": request_id,
            "ok": True,
            "generation": generation,
            "state_hash": state_hash,
            "allocation": allocation_to_dict(allocation),
        }
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
