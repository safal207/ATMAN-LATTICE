from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import os
import sqlite3
from typing import Mapping

from model.active_verification import (
    ActiveVerificationPlanReceipt,
    ActiveVerificationPolicy,
    ExpectedInformationGainReceipt,
    HypothesisState,
    VerificationLikelihoodModel,
    make_active_verification_policy,
    make_hypothesis_state,
    make_likelihood_model,
    plan_active_verification,
)
from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.runtime_economy import (
    _connect as economy_connect,
    _current_economy_state,
    make_economy_policy_from_env,
)
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import verification_scope
from model.verification_economy import VerificationEconomyPolicy

ACTIVE_PROTOCOL = "ATMAN-ACTIVE/1.9"
ACTIVE_OPERATIONS = {
    "register_hypothesis_state",
    "register_likelihood_model",
    "preview_active_plan",
    "finalize_active_plan",
    "get_active_state",
}

ROLE_ACTIVE_MODEL_KEEPER = "ACTIVE_VERIFICATION_MODEL_KEEPER"
ROLE_ACTIVE_PLAN_KEEPER = "ACTIVE_VERIFICATION_PLAN_KEEPER"
GLOBAL_ACTIVE_SCOPE = "active-verification:global"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def hypothesis_to_dict(value: HypothesisState) -> dict[str, object]:
    value.validate()
    return asdict(value)


def hypothesis_from_dict(data: Mapping[str, object]) -> HypothesisState:
    result = HypothesisState(
        hypothesis_ref=str(data["hypothesis_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        true_probability_bps=int(data["true_probability_bps"]),
        evidence_state_hash=str(data["evidence_state_hash"]),
        generation=int(data["generation"]),
        hypothesis_hash=str(data["hypothesis_hash"]),
    )
    result.validate()
    return result


def likelihood_to_dict(value: VerificationLikelihoodModel) -> dict[str, object]:
    value.validate()
    return asdict(value)


def likelihood_from_dict(data: Mapping[str, object]) -> VerificationLikelihoodModel:
    result = VerificationLikelihoodModel(
        candidate_hash=str(data["candidate_hash"]),
        hypothesis_hash=str(data["hypothesis_hash"]),
        positive_if_true_bps=int(data["positive_if_true_bps"]),
        positive_if_false_bps=int(data["positive_if_false_bps"]),
        model_ref=str(data["model_ref"]),
        model_generation=int(data["model_generation"]),
        model_hash=str(data["model_hash"]),
    )
    result.validate()
    return result


def insight_to_dict(value: ExpectedInformationGainReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def plan_to_dict(value: ActiveVerificationPlanReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    for key in (
        "candidate_hashes",
        "information_gain_hashes",
        "ranked_candidate_hashes",
        "selected_candidate_hashes",
        "deferred_budget_candidate_hashes",
        "deferred_oversized_candidate_hashes",
        "deferred_low_information_candidate_hashes",
    ):
        data[key] = list(data[key])
    return data


def make_active_policy_from_env() -> ActiveVerificationPolicy:
    return make_active_verification_policy(
        os.environ.get("ATMAN_ACTIVE_POLICY_REF", "atman:active-verification:runtime:v1.9"),
        budget_units=int(os.environ.get("ATMAN_ACTIVE_BUDGET_UNITS", os.environ.get("ATMAN_VERIFICATION_BUDGET_UNITS", "20"))),
        max_selected_items=int(os.environ.get("ATMAN_ACTIVE_MAX_SELECTED_ITEMS", "10")),
        minimum_information_gain_microbits=int(os.environ.get("ATMAN_ACTIVE_MIN_INFORMATION_GAIN_MICROBITS", "1")),
        aging_quantum=int(os.environ.get("ATMAN_ACTIVE_AGING_QUANTUM", "60")),
        aging_weight=int(os.environ.get("ATMAN_ACTIVE_AGING_WEIGHT", "1")),
        risk_weight=int(os.environ.get("ATMAN_ACTIVE_RISK_WEIGHT", "0")),
    )


def _connect(db_path: str) -> sqlite3.Connection:
    conn = economy_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_hypothesis (
            candidate_hash TEXT PRIMARY KEY,
            hypothesis_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_likelihood_model (
            candidate_hash TEXT PRIMARY KEY,
            model_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_verification_plan (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            generation INTEGER NOT NULL,
            state_hash TEXT NOT NULL,
            runtime_plan_hash TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            unmodeled_json TEXT NOT NULL
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
        raise PermissionError("active verification authority failed: " + ",".join(dict.fromkeys(failures)))


def _candidate_by_hash(conn: sqlite3.Connection, candidate_hash: str):
    state = _current_economy_state(conn, make_economy_policy_from_env())
    for candidate in state["candidates"]:
        if candidate.candidate_hash == candidate_hash:
            return candidate
    raise ValueError("active model must reference current incomplete economic candidate")


def action_register_hypothesis(candidate_hash: str, hypothesis: HypothesisState) -> dict[str, object]:
    hypothesis.validate()
    return {
        "operation": "register_hypothesis_state",
        "candidate_hash": candidate_hash,
        "hypothesis_hash": hypothesis.hypothesis_hash,
        "subject_identity_ref": hypothesis.subject_identity_ref,
        "generation": hypothesis.generation,
    }


def action_register_likelihood(model: VerificationLikelihoodModel, subject_identity_ref: str) -> dict[str, object]:
    model.validate()
    return {
        "operation": "register_likelihood_model",
        "candidate_hash": model.candidate_hash,
        "hypothesis_hash": model.hypothesis_hash,
        "model_hash": model.model_hash,
        "subject_identity_ref": subject_identity_ref,
        "model_generation": model.model_generation,
    }


def action_finalize_active_plan(
    *,
    state_hash: str,
    runtime_plan_hash: str,
    active_policy_hash: str,
    economy_policy_hash: str,
    generation: int,
    finalized_at: int,
) -> dict[str, object]:
    return {
        "operation": "finalize_active_plan",
        "state_hash": state_hash,
        "runtime_plan_hash": runtime_plan_hash,
        "active_policy_hash": active_policy_hash,
        "economy_policy_hash": economy_policy_hash,
        "generation": generation,
        "finalized_at": finalized_at,
    }


def _load_hypotheses(conn: sqlite3.Connection) -> dict[str, HypothesisState]:
    rows = conn.execute("SELECT candidate_hash,hypothesis_json FROM active_hypothesis ORDER BY candidate_hash").fetchall()
    return {str(row[0]): hypothesis_from_dict(json.loads(row[1])) for row in rows}


def _load_models(conn: sqlite3.Connection) -> dict[str, VerificationLikelihoodModel]:
    rows = conn.execute("SELECT candidate_hash,model_json FROM active_likelihood_model ORDER BY candidate_hash").fetchall()
    return {str(row[0]): likelihood_from_dict(json.loads(row[1])) for row in rows}


def _plan_generation(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT generation FROM active_verification_plan WHERE singleton=1").fetchone()
    return 0 if row is None else int(row[0])


def _preview(
    conn: sqlite3.Connection,
    *,
    economy_policy: VerificationEconomyPolicy,
    active_policy: ActiveVerificationPolicy,
    measured_at: int,
) -> dict[str, object]:
    economy_state = _current_economy_state(conn, economy_policy)
    candidates = tuple(economy_state["candidates"])
    estimators = economy_state["estimators"]
    stored_hypotheses = _load_hypotheses(conn)
    stored_models = _load_models(conn)

    modeled = []
    hypotheses = {}
    models = {}
    unmodeled = []
    for candidate in candidates:
        hypothesis = stored_hypotheses.get(candidate.candidate_hash)
        model = stored_models.get(candidate.candidate_hash)
        if (
            hypothesis is None
            or model is None
            or hypothesis.subject_identity_ref != candidate.subject_identity_ref
            or model.candidate_hash != candidate.candidate_hash
            or model.hypothesis_hash != hypothesis.hypothesis_hash
        ):
            unmodeled.append(candidate.candidate_hash)
            continue
        modeled.append(candidate)
        hypotheses[candidate.candidate_hash] = hypothesis
        models[candidate.candidate_hash] = model

    plan, insights = plan_active_verification(
        modeled,
        hypotheses,
        models,
        estimators,
        economy_policy,
        active_policy,
        measured_at=measured_at,
    )
    unmodeled_tuple = tuple(sorted(unmodeled))
    state_material = {
        "domain": "ATMAN-LATTICE/runtime-active-verification-state/v1.9",
        "economy_state_hash": economy_state["state_hash"],
        "active_policy_hash": active_policy.policy_hash,
        "economy_policy_hash": economy_policy.policy_hash,
        "current_candidate_hashes": [item.candidate_hash for item in candidates],
        "hypothesis_hashes": sorted(
            hypothesis.hypothesis_hash
            for candidate_hash, hypothesis in stored_hypotheses.items()
            if candidate_hash in {item.candidate_hash for item in candidates}
        ),
        "likelihood_model_hashes": sorted(
            model.model_hash
            for candidate_hash, model in stored_models.items()
            if candidate_hash in {item.candidate_hash for item in candidates}
        ),
    }
    state_hash = _digest(state_material)
    runtime_plan_hash = _digest({
        "domain": "ATMAN-LATTICE/runtime-active-verification-plan/v1.9",
        "state_hash": state_hash,
        "plan_hash": plan.plan_hash,
        "unmodeled_candidate_hashes": list(unmodeled_tuple),
    })
    return {
        "state_hash": state_hash,
        "runtime_plan_hash": runtime_plan_hash,
        "plan": plan,
        "insights": insights,
        "unmodeled_candidate_hashes": unmodeled_tuple,
    }


def _register_hypothesis(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> HypothesisState:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _candidate_by_hash(conn, candidate_hash)
    hypothesis = make_hypothesis_state(
        str(payload["hypothesis_ref"]),
        subject_identity_ref=candidate.subject_identity_ref,
        true_probability_bps=int(payload["true_probability_bps"]),
        evidence_state_hash=str(payload["evidence_state_hash"]),
        generation=int(payload["generation"]),
    )
    _enforce(
        grant,
        proof,
        action=action_register_hypothesis(candidate_hash, hypothesis),
        required_role=ROLE_ACTIVE_MODEL_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT hypothesis_json FROM active_hypothesis WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    encoded = json.dumps(hypothesis_to_dict(hypothesis), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = hypothesis_from_dict(json.loads(existing[0]))
        if current == hypothesis:
            return current
        if hypothesis.generation <= current.generation:
            raise ValueError("hypothesis generation must advance monotonically")
        conn.execute("UPDATE active_hypothesis SET hypothesis_json=? WHERE candidate_hash=?", (encoded, candidate_hash))
        return hypothesis
    conn.execute("INSERT INTO active_hypothesis(candidate_hash,hypothesis_json) VALUES(?,?)", (candidate_hash, encoded))
    return hypothesis


def _register_likelihood(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> VerificationLikelihoodModel:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _candidate_by_hash(conn, candidate_hash)
    hypothesis_row = conn.execute("SELECT hypothesis_json FROM active_hypothesis WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if hypothesis_row is None:
        raise ValueError("likelihood model requires current hypothesis state")
    hypothesis = hypothesis_from_dict(json.loads(hypothesis_row[0]))
    model = make_likelihood_model(
        candidate_hash=candidate_hash,
        hypothesis_hash=hypothesis.hypothesis_hash,
        positive_if_true_bps=int(payload["positive_if_true_bps"]),
        positive_if_false_bps=int(payload["positive_if_false_bps"]),
        model_ref=str(payload["model_ref"]),
        model_generation=int(payload["model_generation"]),
    )
    _enforce(
        grant,
        proof,
        action=action_register_likelihood(model, candidate.subject_identity_ref),
        required_role=ROLE_ACTIVE_MODEL_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT model_json FROM active_likelihood_model WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    encoded = json.dumps(likelihood_to_dict(model), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = likelihood_from_dict(json.loads(existing[0]))
        if current == model:
            return current
        if model.model_generation <= current.model_generation:
            raise ValueError("likelihood model generation must advance monotonically")
        conn.execute("UPDATE active_likelihood_model SET model_json=? WHERE candidate_hash=?", (encoded, candidate_hash))
        return model
    conn.execute("INSERT INTO active_likelihood_model(candidate_hash,model_json) VALUES(?,?)", (candidate_hash, encoded))
    return model


def execute_active_request(
    request: Mapping[str, object],
    *,
    enforcement: EnforcementContext,
    db_path: str,
    economy_policy: VerificationEconomyPolicy,
    active_policy: ActiveVerificationPolicy,
) -> dict[str, object]:
    if request.get("protocol") != ACTIVE_PROTOCOL:
        raise ValueError("unsupported active verification protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in ACTIVE_OPERATIONS:
        raise ValueError("unsupported active verification operation")
    payload = _mapping(request.get("payload", {}), "payload")
    economy_policy.validate()
    active_policy.validate()
    conn = _connect(db_path)
    try:
        if operation in {"get_active_state", "preview_active_plan"}:
            preview = _preview(conn, economy_policy=economy_policy, active_policy=active_policy, measured_at=enforcement.now)
            return {
                "protocol": ACTIVE_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "generation": _plan_generation(conn),
                "state_hash": preview["state_hash"],
                "runtime_plan_hash": preview["runtime_plan_hash"],
                "plan": plan_to_dict(preview["plan"]),
                "insights": [insight_to_dict(item) for item in preview["insights"]],
                "unmodeled_candidate_hashes": list(preview["unmodeled_candidate_hashes"]),
            }

        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")

        if operation == "register_hypothesis_state":
            hypothesis = _register_hypothesis(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {
                "protocol": ACTIVE_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "hypothesis": hypothesis_to_dict(hypothesis),
            }

        if operation == "register_likelihood_model":
            model = _register_likelihood(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {
                "protocol": ACTIVE_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "likelihood_model": likelihood_to_dict(model),
            }

        expected_state_hash = str(payload.get("expected_state_hash", ""))
        expected_runtime_plan_hash = str(payload.get("expected_runtime_plan_hash", ""))
        if not expected_state_hash or not expected_runtime_plan_hash:
            raise ValueError("expected_state_hash and expected_runtime_plan_hash are required")
        preview = _preview(conn, economy_policy=economy_policy, active_policy=active_policy, measured_at=enforcement.now)
        if preview["state_hash"] != expected_state_hash or preview["runtime_plan_hash"] != expected_runtime_plan_hash:
            raise PermissionError("stale active verification state")
        generation = _plan_generation(conn) + 1
        action = action_finalize_active_plan(
            state_hash=str(preview["state_hash"]),
            runtime_plan_hash=str(preview["runtime_plan_hash"]),
            active_policy_hash=active_policy.policy_hash,
            economy_policy_hash=economy_policy.policy_hash,
            generation=generation,
            finalized_at=enforcement.now,
        )
        _enforce(
            grant,
            proof,
            action=action,
            required_role=ROLE_ACTIVE_PLAN_KEEPER,
            required_scope=GLOBAL_ACTIVE_SCOPE,
            enforcement=enforcement,
        )
        encoded_plan = json.dumps(plan_to_dict(preview["plan"]), sort_keys=True, separators=(",", ":"))
        encoded_unmodeled = json.dumps(list(preview["unmodeled_candidate_hashes"]), sort_keys=True, separators=(",", ":"))
        conn.execute(
            """
            INSERT INTO active_verification_plan(singleton,generation,state_hash,runtime_plan_hash,plan_json,unmodeled_json)
            VALUES(1,?,?,?,?,?)
            ON CONFLICT(singleton) DO UPDATE SET
                generation=excluded.generation,
                state_hash=excluded.state_hash,
                runtime_plan_hash=excluded.runtime_plan_hash,
                plan_json=excluded.plan_json,
                unmodeled_json=excluded.unmodeled_json
            """,
            (generation, preview["state_hash"], preview["runtime_plan_hash"], encoded_plan, encoded_unmodeled),
        )
        conn.execute("COMMIT")
        return {
            "protocol": ACTIVE_PROTOCOL,
            "request_id": request_id,
            "ok": True,
            "generation": generation,
            "state_hash": preview["state_hash"],
            "runtime_plan_hash": preview["runtime_plan_hash"],
            "plan": plan_to_dict(preview["plan"]),
            "insights": [insight_to_dict(item) for item in preview["insights"]],
            "unmodeled_candidate_hashes": list(preview["unmodeled_candidate_hashes"]),
        }
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
