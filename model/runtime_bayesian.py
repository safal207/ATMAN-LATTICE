from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from typing import Mapping

from model.active_verification import ActiveVerificationPolicy, HypothesisState, VerificationLikelihoodModel
from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.bayesian_evidence import (
    BayesianUpdateReceipt,
    EvidenceInterpretationReceipt,
    EvidenceInterpretationRule,
    LikelihoodRebaseReceipt,
    build_bayesian_update,
    interpret_completion,
    make_interpretation_rule,
    rebase_likelihood_model,
)
from model.enforcement import EnforcementContext
from model.runtime_active_verification import (
    _connect as active_connect,
    _preview as active_preview,
    hypothesis_from_dict,
    hypothesis_to_dict,
    insight_to_dict,
    likelihood_from_dict,
    likelihood_to_dict,
    plan_to_dict,
)
from model.runtime_economy import candidate_from_dict
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import completion_from_dict, verification_scope
from model.verification_economy import VerificationEconomyPolicy

BAYES_PROTOCOL = "ATMAN-BAYES/1.10"
BAYES_OPERATIONS = {
    "register_interpretation_rule",
    "preview_bayesian_update",
    "apply_bayesian_update",
}

ROLE_BAYES_RULE_KEEPER = "BAYESIAN_INTERPRETATION_RULE_KEEPER"
ROLE_BAYES_UPDATE_KEEPER = "BAYESIAN_UPDATE_KEEPER"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def rule_to_dict(value: EvidenceInterpretationRule) -> dict[str, object]:
    value.validate()
    return asdict(value)


def rule_from_dict(data: Mapping[str, object]) -> EvidenceInterpretationRule:
    result = EvidenceInterpretationRule(
        candidate_hash=str(data["candidate_hash"]),
        likelihood_model_hash=str(data["likelihood_model_hash"]),
        pass_outcome=str(data["pass_outcome"]),
        hold_outcome=str(data["hold_outcome"]),
        fail_outcome=str(data["fail_outcome"]),
        rule_ref=str(data["rule_ref"]),
        rule_generation=int(data["rule_generation"]),
        registered_at=int(data["registered_at"]),
        rule_hash=str(data["rule_hash"]),
    )
    result.validate()
    return result


def interpretation_to_dict(value: EvidenceInterpretationReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def update_to_dict(value: BayesianUpdateReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def rebase_to_dict(value: LikelihoodRebaseReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = active_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bayesian_interpretation_rule (
            candidate_hash TEXT PRIMARY KEY,
            rule_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bayesian_interpretation_history (
            interpretation_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL,
            completion_hash TEXT NOT NULL UNIQUE,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bayesian_update_history (
            update_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL,
            prior_hypothesis_hash TEXT NOT NULL UNIQUE,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bayesian_likelihood_rebase_history (
            rebase_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL,
            receipt_json TEXT NOT NULL
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
        raise PermissionError("bayesian evidence authority failed: " + ",".join(dict.fromkeys(failures)))


def _candidate_by_hash(conn: sqlite3.Connection, candidate_hash: str):
    rows = conn.execute("SELECT candidate_json FROM verification_economy_candidate ORDER BY work_hash").fetchall()
    for row in rows:
        candidate = candidate_from_dict(json.loads(row[0]))
        if candidate.candidate_hash == candidate_hash:
            return candidate
    raise ValueError("unknown economic candidate")


def _hypothesis(conn: sqlite3.Connection, candidate_hash: str) -> HypothesisState:
    row = conn.execute("SELECT hypothesis_json FROM active_hypothesis WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("bayesian update requires current hypothesis state")
    return hypothesis_from_dict(json.loads(row[0]))


def _likelihood(conn: sqlite3.Connection, candidate_hash: str) -> VerificationLikelihoodModel:
    row = conn.execute("SELECT model_json FROM active_likelihood_model WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("bayesian update requires current likelihood model")
    return likelihood_from_dict(json.loads(row[0]))


def _rule(conn: sqlite3.Connection, candidate_hash: str) -> EvidenceInterpretationRule:
    row = conn.execute("SELECT rule_json FROM bayesian_interpretation_rule WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("bayesian update requires precommitted interpretation rule")
    return rule_from_dict(json.loads(row[0]))


def _completion(conn: sqlite3.Connection, work_hash: str):
    row = conn.execute("SELECT completion_json FROM verification_work WHERE work_hash=?", (work_hash,)).fetchone()
    if row is None:
        raise ValueError("candidate verification work does not exist")
    if row[0] is None:
        raise ValueError("bayesian update requires completed verification work")
    return completion_from_dict(json.loads(row[0]))


def action_register_interpretation_rule(rule: EvidenceInterpretationRule, subject_identity_ref: str) -> dict[str, object]:
    rule.validate()
    return {
        "operation": "register_interpretation_rule",
        "candidate_hash": rule.candidate_hash,
        "likelihood_model_hash": rule.likelihood_model_hash,
        "rule_hash": rule.rule_hash,
        "subject_identity_ref": subject_identity_ref,
        "rule_generation": rule.rule_generation,
        "registered_at": rule.registered_at,
    }


def action_apply_bayesian_update(
    *,
    state_hash: str,
    interpretation_hash: str,
    update_hash: str,
    posterior_hypothesis_hash: str,
    rebase_hashes: tuple[str, ...],
    applied_at: int,
) -> dict[str, object]:
    return {
        "operation": "apply_bayesian_update",
        "state_hash": state_hash,
        "interpretation_hash": interpretation_hash,
        "update_hash": update_hash,
        "posterior_hypothesis_hash": posterior_hypothesis_hash,
        "rebase_hashes": list(rebase_hashes),
        "applied_at": applied_at,
    }


def _register_rule(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> EvidenceInterpretationRule:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _candidate_by_hash(conn, candidate_hash)
    completion_row = conn.execute("SELECT completion_json FROM verification_work WHERE work_hash=?", (candidate.work_hash,)).fetchone()
    if completion_row is None:
        raise ValueError("candidate verification work does not exist")
    if completion_row[0] is not None:
        raise ValueError("interpretation rule must be registered before verification completion")
    hypothesis = _hypothesis(conn, candidate_hash)
    model = _likelihood(conn, candidate_hash)
    if model.hypothesis_hash != hypothesis.hypothesis_hash:
        raise ValueError("interpretation rule requires current likelihood/hypothesis binding")
    rule = make_interpretation_rule(
        candidate_hash=candidate_hash,
        likelihood_model_hash=model.model_hash,
        pass_outcome=str(payload["pass_outcome"]),
        hold_outcome=str(payload["hold_outcome"]),
        fail_outcome=str(payload["fail_outcome"]),
        rule_ref=str(payload["rule_ref"]),
        rule_generation=int(payload["rule_generation"]),
        registered_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_register_interpretation_rule(rule, candidate.subject_identity_ref),
        required_role=ROLE_BAYES_RULE_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT rule_json FROM bayesian_interpretation_rule WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    encoded = json.dumps(rule_to_dict(rule), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = rule_from_dict(json.loads(existing[0]))
        if current == rule:
            return current
        if rule.rule_generation <= current.rule_generation:
            raise ValueError("interpretation rule generation must advance monotonically")
        conn.execute("UPDATE bayesian_interpretation_rule SET rule_json=? WHERE candidate_hash=?", (encoded, candidate_hash))
        return rule
    conn.execute("INSERT INTO bayesian_interpretation_rule(candidate_hash,rule_json) VALUES(?,?)", (candidate_hash, encoded))
    return rule


def _cohort(conn: sqlite3.Connection, prior_hypothesis_hash: str) -> tuple[tuple[str, HypothesisState, VerificationLikelihoodModel | None], ...]:
    rows = conn.execute("SELECT candidate_hash,hypothesis_json FROM active_hypothesis ORDER BY candidate_hash").fetchall()
    result = []
    for candidate_hash, hypothesis_json in rows:
        hypothesis = hypothesis_from_dict(json.loads(hypothesis_json))
        if hypothesis.hypothesis_hash != prior_hypothesis_hash:
            continue
        model_row = conn.execute("SELECT model_json FROM active_likelihood_model WHERE candidate_hash=?", (candidate_hash,)).fetchone()
        model = None if model_row is None else likelihood_from_dict(json.loads(model_row[0]))
        result.append((str(candidate_hash), hypothesis, model))
    return tuple(result)


def _preview_update(
    conn: sqlite3.Connection,
    candidate_hash: str,
    *,
    updater_ref: str,
    now: int,
) -> dict[str, object]:
    if not updater_ref:
        raise ValueError("updater_ref is required for Bayesian preview")
    candidate = _candidate_by_hash(conn, candidate_hash)
    prior = _hypothesis(conn, candidate_hash)
    model = _likelihood(conn, candidate_hash)
    rule = _rule(conn, candidate_hash)
    completion = _completion(conn, candidate.work_hash)
    interpretation = interpret_completion(
        candidate_hash=candidate_hash,
        work_hash=candidate.work_hash,
        completion_hash=completion.completion_hash,
        completion_decision=completion.decision,
        prior_hypothesis=prior,
        likelihood_model=model,
        rule=rule,
        completion_completed_at=completion.completed_at,
        interpreted_at=now,
    )
    posterior, update = build_bayesian_update(
        candidate_hash=candidate_hash,
        prior_hypothesis=prior,
        likelihood_model=model,
        interpretation=interpretation,
        applied_at=now,
        updater_ref=updater_ref,
    )
    cohort = _cohort(conn, prior.hypothesis_hash)
    rebased_models = []
    rebases = []
    for cohort_candidate_hash, _, cohort_model in cohort:
        if cohort_model is None or cohort_model.hypothesis_hash != prior.hypothesis_hash:
            continue
        rebased, rebase = rebase_likelihood_model(cohort_model, posterior_hypothesis=posterior, rebased_at=now)
        rebased_models.append((cohort_candidate_hash, rebased))
        rebases.append(rebase)
    state_material = {
        "domain": "ATMAN-LATTICE/runtime-bayesian-evidence-state/v1.10",
        "candidate_hash": candidate_hash,
        "completion_hash": completion.completion_hash,
        "prior_hypothesis_hash": prior.hypothesis_hash,
        "likelihood_model_hash": model.model_hash,
        "rule_hash": rule.rule_hash,
        "cohort_candidate_hashes": [item[0] for item in cohort],
        "cohort_model_hashes": sorted(
            item[2].model_hash for item in cohort if item[2] is not None
        ),
    }
    return {
        "state_hash": _digest(state_material),
        "candidate": candidate,
        "prior": prior,
        "model": model,
        "rule": rule,
        "completion": completion,
        "interpretation": interpretation,
        "posterior": posterior,
        "update": update,
        "cohort": cohort,
        "rebased_models": tuple(rebased_models),
        "rebases": tuple(rebases),
    }


def execute_bayesian_request(
    request: Mapping[str, object],
    *,
    enforcement: EnforcementContext,
    db_path: str,
    economy_policy: VerificationEconomyPolicy,
    active_policy: ActiveVerificationPolicy,
) -> dict[str, object]:
    if request.get("protocol") != BAYES_PROTOCOL:
        raise ValueError("unsupported Bayesian evidence protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in BAYES_OPERATIONS:
        raise ValueError("unsupported Bayesian evidence operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "preview_bayesian_update":
            preview = _preview_update(
                conn,
                str(payload["candidate_hash"]),
                updater_ref=str(payload["updater_ref"]),
                now=enforcement.now,
            )
            return {
                "protocol": BAYES_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "state_hash": preview["state_hash"],
                "interpretation": interpretation_to_dict(preview["interpretation"]),
                "posterior_hypothesis": hypothesis_to_dict(preview["posterior"]),
                "update": update_to_dict(preview["update"]),
                "rebases": [rebase_to_dict(item) for item in preview["rebases"]],
            }

        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")

        if operation == "register_interpretation_rule":
            rule = _register_rule(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {
                "protocol": BAYES_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "rule": rule_to_dict(rule),
            }

        candidate_hash = str(payload["candidate_hash"])
        expected_state_hash = str(payload.get("expected_state_hash", ""))
        expected_interpretation_hash = str(payload.get("expected_interpretation_hash", ""))
        expected_update_hash = str(payload.get("expected_update_hash", ""))
        if not expected_state_hash or not expected_interpretation_hash or not expected_update_hash:
            raise ValueError("expected Bayesian state, interpretation, and update hashes are required")
        preview = _preview_update(conn, candidate_hash, updater_ref=grant.subject_ref, now=enforcement.now)
        if preview["state_hash"] != expected_state_hash:
            raise PermissionError("stale Bayesian evidence state")
        if preview["interpretation"].interpretation_hash != expected_interpretation_hash:
            raise PermissionError("stale Bayesian evidence interpretation")
        if preview["update"].update_hash != expected_update_hash:
            raise PermissionError("stale Bayesian posterior update")
        rebase_hashes = tuple(sorted(item.rebase_hash for item in preview["rebases"]))
        action = action_apply_bayesian_update(
            state_hash=str(preview["state_hash"]),
            interpretation_hash=preview["interpretation"].interpretation_hash,
            update_hash=preview["update"].update_hash,
            posterior_hypothesis_hash=preview["posterior"].hypothesis_hash,
            rebase_hashes=rebase_hashes,
            applied_at=enforcement.now,
        )
        _enforce(
            grant,
            proof,
            action=action,
            required_role=ROLE_BAYES_UPDATE_KEEPER,
            required_scope=verification_scope(preview["candidate"].subject_identity_ref),
            enforcement=enforcement,
        )
        if conn.execute("SELECT 1 FROM bayesian_interpretation_history WHERE completion_hash=?", (preview["completion"].completion_hash,)).fetchone() is not None:
            raise ValueError("verification completion has already been interpreted")
        if conn.execute("SELECT 1 FROM bayesian_update_history WHERE prior_hypothesis_hash=?", (preview["prior"].hypothesis_hash,)).fetchone() is not None:
            raise ValueError("prior hypothesis has already been advanced")

        posterior_json = json.dumps(hypothesis_to_dict(preview["posterior"]), sort_keys=True, separators=(",", ":"))
        cohort_hashes = {item[0] for item in preview["cohort"]}
        for cohort_candidate_hash in cohort_hashes:
            conn.execute("UPDATE active_hypothesis SET hypothesis_json=? WHERE candidate_hash=?", (posterior_json, cohort_candidate_hash))
        for cohort_candidate_hash, rebased in preview["rebased_models"]:
            conn.execute(
                "UPDATE active_likelihood_model SET model_json=? WHERE candidate_hash=?",
                (json.dumps(likelihood_to_dict(rebased), sort_keys=True, separators=(",", ":")), cohort_candidate_hash),
            )

        conn.execute(
            "INSERT INTO bayesian_interpretation_history(interpretation_hash,candidate_hash,completion_hash,receipt_json) VALUES(?,?,?,?)",
            (
                preview["interpretation"].interpretation_hash,
                candidate_hash,
                preview["completion"].completion_hash,
                json.dumps(interpretation_to_dict(preview["interpretation"]), sort_keys=True, separators=(",", ":")),
            ),
        )
        conn.execute(
            "INSERT INTO bayesian_update_history(update_hash,candidate_hash,prior_hypothesis_hash,receipt_json) VALUES(?,?,?,?)",
            (
                preview["update"].update_hash,
                candidate_hash,
                preview["prior"].hypothesis_hash,
                json.dumps(update_to_dict(preview["update"]), sort_keys=True, separators=(",", ":")),
            ),
        )
        for rebase in preview["rebases"]:
            conn.execute(
                "INSERT INTO bayesian_likelihood_rebase_history(rebase_hash,candidate_hash,receipt_json) VALUES(?,?,?)",
                (rebase.rebase_hash, rebase.candidate_hash, json.dumps(rebase_to_dict(rebase), sort_keys=True, separators=(",", ":"))),
            )

        next_active = active_preview(
            conn,
            economy_policy=economy_policy,
            active_policy=active_policy,
            measured_at=enforcement.now,
        )
        conn.execute("COMMIT")
        return {
            "protocol": BAYES_PROTOCOL,
            "request_id": request_id,
            "ok": True,
            "state_hash": preview["state_hash"],
            "interpretation": interpretation_to_dict(preview["interpretation"]),
            "posterior_hypothesis": hypothesis_to_dict(preview["posterior"]),
            "update": update_to_dict(preview["update"]),
            "rebases": [rebase_to_dict(item) for item in preview["rebases"]],
            "next_active_state_hash": next_active["state_hash"],
            "next_runtime_plan_hash": next_active["runtime_plan_hash"],
            "next_active_plan": plan_to_dict(next_active["plan"]),
            "next_active_insights": [insight_to_dict(item) for item in next_active["insights"]],
            "next_unmodeled_candidate_hashes": list(next_active["unmodeled_candidate_hashes"]),
        }
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
