from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.protected_confirmation import ConfirmedGraphRevisionReceipt
from model.replication import (
    ReplicationBatch,
    ReplicationEvaluationReceipt,
    ReplicationPolicy,
    ReplicationReviewReceipt,
    ReplicationSeriesSnapshot,
    ReplicationTargetReceipt,
    assert_replication_freshness,
    evaluate_replication,
    make_replication_batch,
    make_replication_policy,
    make_replication_target,
    review_replication,
    summarize_replication_series,
)
from model.runtime_calibration import pair_from_dict, pair_to_dict
from model.runtime_dependency_graph import _graph, _pair_samples, graph_from_dict
from model.runtime_protected_confirmation import (
    _connect as confirm_connect,
    batch_from_dict as confirmation_batch_from_dict,
    evaluation_from_dict as confirmation_evaluation_from_dict,
    review_from_dict as confirmation_review_from_dict,
)
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_structural_validation import _policy as structural_policy, candidate_from_dict
from model.runtime_verification import verification_scope

REPLICATION_PROTOCOL = "ATMAN-REPLICATE/1.18"
REPLICATION_OPERATIONS = {
    "register_replication_policy",
    "register_replication_target",
    "seal_replication_batch",
    "evaluate_replication",
    "record_replication_review",
    "finalize_replication_snapshot",
    "get_replication_state",
}

ROLE_REPLICATION_POLICY_KEEPER = "REPLICATION_POLICY_KEEPER"
ROLE_REPLICATION_TARGET_KEEPER = "REPLICATION_TARGET_KEEPER"
ROLE_REPLICATION_BATCH_KEEPER = "REPLICATION_BATCH_KEEPER"
ROLE_REPLICATION_EVALUATOR = "REPLICATION_EVALUATOR"
ROLE_REPLICATION_REVIEWER = "REPLICATION_REVIEWER"
ROLE_REPLICATION_MONITOR_KEEPER = "REPLICATION_MONITOR_KEEPER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def policy_to_dict(value: ReplicationPolicy) -> dict[str, object]:
    value.validate(); return asdict(value)


def policy_from_dict(data: Mapping[str, object]) -> ReplicationPolicy:
    result = ReplicationPolicy(
        policy_ref=str(data["policy_ref"]), subject_identity_ref=str(data["subject_identity_ref"]),
        min_replication_samples=int(data["min_replication_samples"]), min_temporal_gap=int(data["min_temporal_gap"]),
        min_regularized_improvement_ppm=int(data["min_regularized_improvement_ppm"]),
        max_proposed_brier_degradation_ppm=int(data["max_proposed_brier_degradation_ppm"]),
        persistent_drift_epochs=int(data["persistent_drift_epochs"]), registered_at=int(data["registered_at"]),
        policy_hash=str(data["policy_hash"]),
    )
    result.validate(); return result


def target_to_dict(value: ReplicationTargetReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def target_from_dict(data: Mapping[str, object]) -> ReplicationTargetReceipt:
    result = ReplicationTargetReceipt(
        target_ref=str(data["target_ref"]), subject_identity_ref=str(data["subject_identity_ref"]), pair_key=str(data["pair_key"]),
        confirmed_revision_hash=str(data["confirmed_revision_hash"]), candidate_hash=str(data["candidate_hash"]),
        confirmed_graph_hash=str(data["confirmed_graph_hash"]), confirmed_generation=int(data["confirmed_generation"]),
        confirmation_evaluation_hash=str(data["confirmation_evaluation_hash"]), confirmation_review_hash=str(data["confirmation_review_hash"]),
        confirmation_batch_hash=str(data["confirmation_batch_hash"]), confirmation_source_ref=str(data["confirmation_source_ref"]),
        confirmation_evaluated_at=int(data["confirmation_evaluated_at"]), baseline_proposed_mean_brier_ppm=int(data["baseline_proposed_mean_brier_ppm"]),
        baseline_regularized_improvement_ppm=int(data["baseline_regularized_improvement_ppm"]), candidate_proposer_ref=str(data["candidate_proposer_ref"]),
        confirmation_evaluator_ref=str(data["confirmation_evaluator_ref"]), confirmation_reviewer_ref=str(data["confirmation_reviewer_ref"]),
        registered_at=int(data["registered_at"]), target_hash=str(data["target_hash"]),
    )
    result.validate(); return result


def batch_to_dict(value: ReplicationBatch) -> dict[str, object]:
    value.validate(); data = asdict(value)
    data["sample_hashes"] = list(value.sample_hashes); data["resolution_hashes"] = list(value.resolution_hashes); data["evidence_hashes"] = list(value.evidence_hashes)
    return data


def batch_from_dict(data: Mapping[str, object]) -> ReplicationBatch:
    result = ReplicationBatch(
        batch_ref=str(data["batch_ref"]), target_hash=str(data["target_hash"]), subject_identity_ref=str(data["subject_identity_ref"]),
        pair_key=str(data["pair_key"]), mode=str(data["mode"]), source_ref=str(data["source_ref"]), environment_ref=str(data["environment_ref"]),
        collected_from=int(data["collected_from"]), collected_to=int(data["collected_to"]), generation=int(data["generation"]),
        previous_batch_hash=None if data.get("previous_batch_hash") is None else str(data["previous_batch_hash"]),
        sample_hashes=tuple(str(v) for v in data.get("sample_hashes", [])), resolution_hashes=tuple(str(v) for v in data.get("resolution_hashes", [])),
        evidence_hashes=tuple(str(v) for v in data.get("evidence_hashes", [])), sample_count=int(data["sample_count"]),
        batch_keeper_ref=str(data["batch_keeper_ref"]), sealed_at=int(data["sealed_at"]), batch_hash=str(data["batch_hash"]),
    )
    result.validate(); return result


def evaluation_to_dict(value: ReplicationEvaluationReceipt) -> dict[str, object]:
    value.validate(); data = asdict(value); data["case_hashes"] = list(value.case_hashes); return data


def evaluation_from_dict(data: Mapping[str, object]) -> ReplicationEvaluationReceipt:
    nullable = lambda key: None if data.get(key) is None else int(data[key])
    result = ReplicationEvaluationReceipt(
        target_hash=str(data["target_hash"]), batch_hash=str(data["batch_hash"]), batch_generation=int(data["batch_generation"]),
        mode=str(data["mode"]), source_ref=str(data["source_ref"]), environment_ref=str(data["environment_ref"]), policy_hash=str(data["policy_hash"]),
        confirmed_revision_hash=str(data["confirmed_revision_hash"]), candidate_hash=str(data["candidate_hash"]), confirmed_graph_hash=str(data["confirmed_graph_hash"]),
        case_hashes=tuple(str(v) for v in data.get("case_hashes", [])), evaluated_case_count=int(data["evaluated_case_count"]), min_replication_samples=int(data["min_replication_samples"]),
        temporal_gap=int(data["temporal_gap"]), base_mean_brier_ppm=nullable("base_mean_brier_ppm"), confirmed_mean_brier_ppm=nullable("confirmed_mean_brier_ppm"),
        base_regularized_brier_ppm=nullable("base_regularized_brier_ppm"), confirmed_regularized_brier_ppm=nullable("confirmed_regularized_brier_ppm"),
        regularized_improvement_ppm=nullable("regularized_improvement_ppm"), baseline_confirmed_mean_brier_ppm=int(data["baseline_confirmed_mean_brier_ppm"]),
        proposed_brier_degradation_ppm=nullable("proposed_brier_degradation_ppm"), allowed_brier_degradation_ppm=int(data["allowed_brier_degradation_ppm"]),
        required_min_regularized_improvement_ppm=int(data["required_min_regularized_improvement_ppm"]), drift_kind=str(data["drift_kind"]), status=str(data["status"]),
        batch_keeper_ref=str(data["batch_keeper_ref"]), evaluator_ref=str(data["evaluator_ref"]), evaluated_at=int(data["evaluated_at"]), evaluation_hash=str(data["evaluation_hash"]),
    )
    result.validate(); return result


def review_to_dict(value: ReplicationReviewReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> ReplicationReviewReceipt:
    result = ReplicationReviewReceipt(
        evaluation_hash=str(data["evaluation_hash"]), target_hash=str(data["target_hash"]), batch_hash=str(data["batch_hash"]),
        status=str(data["status"]), drift_kind=str(data["drift_kind"]), decision=str(data["decision"]), rationale_ref=str(data["rationale_ref"]),
        batch_keeper_ref=str(data["batch_keeper_ref"]), evaluator_ref=str(data["evaluator_ref"]), reviewer_ref=str(data["reviewer_ref"]),
        reviewed_at=int(data["reviewed_at"]), review_hash=str(data["review_hash"]),
    )
    result.validate(); return result


def snapshot_to_dict(value: ReplicationSeriesSnapshot) -> dict[str, object]:
    value.validate(); data = asdict(value); data["evaluation_hashes"] = list(value.evaluation_hashes); data["review_hashes"] = list(value.review_hashes); return data


def confirmed_revision_from_dict(data: Mapping[str, object]) -> ConfirmedGraphRevisionReceipt:
    result = ConfirmedGraphRevisionReceipt(
        selection_hash=str(data["selection_hash"]), search_review_hash=str(data["search_review_hash"]), exposure_hash=str(data["exposure_hash"]),
        confirmation_evaluation_hash=str(data["confirmation_evaluation_hash"]), confirmation_review_hash=str(data["confirmation_review_hash"]),
        candidate_hash=str(data["candidate_hash"]), underlying_search_revision_hash=str(data["underlying_search_revision_hash"]),
        base_graph_hash=str(data["base_graph_hash"]), new_graph_hash=str(data["new_graph_hash"]), base_generation=int(data["base_generation"]),
        new_generation=int(data["new_generation"]), applier_ref=str(data["applier_ref"]), applied_at=int(data["applied_at"]), revision_hash=str(data["revision_hash"]),
    )
    result.validate(); return result


def _connect(db_path: str) -> sqlite3.Connection:
    conn = confirm_connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS replication_policy (subject_identity_ref TEXT PRIMARY KEY, policy_ref TEXT NOT NULL UNIQUE, policy_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS replication_target (target_hash TEXT PRIMARY KEY, target_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, pair_key TEXT NOT NULL, confirmed_revision_hash TEXT NOT NULL UNIQUE, target_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS replication_batch (batch_hash TEXT PRIMARY KEY, batch_ref TEXT NOT NULL UNIQUE, target_hash TEXT NOT NULL, generation INTEGER NOT NULL, batch_json TEXT NOT NULL, samples_json TEXT NOT NULL, UNIQUE(target_hash,generation))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS replication_evaluation (evaluation_hash TEXT PRIMARY KEY, batch_hash TEXT NOT NULL UNIQUE, target_hash TEXT NOT NULL, evaluation_json TEXT NOT NULL, cases_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS replication_review (review_hash TEXT PRIMARY KEY, evaluation_hash TEXT NOT NULL UNIQUE, target_hash TEXT NOT NULL, review_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS replication_snapshot (snapshot_hash TEXT PRIMARY KEY, target_hash TEXT NOT NULL, replication_count INTEGER NOT NULL, snapshot_json TEXT NOT NULL, UNIQUE(target_hash,replication_count))""")
    return conn


def _enforce(grant: AuthorityGrant, proof: AuthorityProof, *, action: object, required_role: str, required_scope: str, enforcement: EnforcementContext) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(grant, proof, action=action, trusted_issuer_keys=enforcement.trusted_issuer_keys, current_policy_generation=enforcement.policy_generation, now=enforcement.now)
    failures = list(limitations)
    if proof.role != required_role: failures.append("required_role_mismatch")
    if proof.scope != required_scope: failures.append("required_scope_mismatch")
    if not valid or failures: raise PermissionError("replication authority failed: " + ",".join(dict.fromkeys(failures)))


def _policy(conn: sqlite3.Connection, subject: str) -> ReplicationPolicy:
    row = conn.execute("SELECT policy_json FROM replication_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is None: raise ValueError("replication policy is not registered")
    return policy_from_dict(json.loads(row[0]))


def _target(conn: sqlite3.Connection, target_hash: str) -> ReplicationTargetReceipt:
    row = conn.execute("SELECT target_json FROM replication_target WHERE target_hash=?", (target_hash,)).fetchone()
    if row is None: raise ValueError("unknown replication target")
    return target_from_dict(json.loads(row[0]))


def _batch(conn: sqlite3.Connection, batch_hash: str):
    row = conn.execute("SELECT batch_json,samples_json FROM replication_batch WHERE batch_hash=?", (batch_hash,)).fetchone()
    if row is None: raise ValueError("unknown replication batch")
    return batch_from_dict(json.loads(row[0])), tuple(pair_from_dict(item) for item in json.loads(row[1]))


def _prior_batches(conn: sqlite3.Connection, target_hash: str) -> tuple[ReplicationBatch, ...]:
    rows = conn.execute("SELECT batch_json FROM replication_batch WHERE target_hash=? ORDER BY generation", (target_hash,)).fetchall()
    return tuple(batch_from_dict(json.loads(row[0])) for row in rows)


def _confirmation_batches(conn: sqlite3.Connection, subject: str, pair_key: str):
    rows = conn.execute("SELECT batch_json FROM protected_confirmation_batch WHERE subject_identity_ref=? AND pair_key=? ORDER BY batch_hash", (subject, pair_key)).fetchall()
    return tuple(confirmation_batch_from_dict(json.loads(row[0])) for row in rows)


def _evaluation(conn: sqlite3.Connection, evaluation_hash: str) -> ReplicationEvaluationReceipt:
    row = conn.execute("SELECT evaluation_json FROM replication_evaluation WHERE evaluation_hash=?", (evaluation_hash,)).fetchone()
    if row is None: raise ValueError("unknown replication evaluation")
    return evaluation_from_dict(json.loads(row[0]))


def _confirmed_bundle(conn: sqlite3.Connection, revision_hash: str):
    row = conn.execute("""
        SELECT base_graph_json,new_graph_json,batch_json,confirmation_evaluation_json,confirmation_review_json,candidate_json,revision_json
        FROM protected_confirmation_revision_history WHERE revision_hash=?
    """, (revision_hash,)).fetchone()
    if row is None: raise ValueError("replication requires an applied v1.17 confirmed graph revision")
    base_graph = graph_from_dict(json.loads(row[0])); confirmed_graph = graph_from_dict(json.loads(row[1]))
    confirmation_batch = confirmation_batch_from_dict(json.loads(row[2]))
    confirmation_evaluation = confirmation_evaluation_from_dict(json.loads(row[3]))
    confirmation_review = confirmation_review_from_dict(json.loads(row[4]))
    candidate = candidate_from_dict(json.loads(row[5])); revision = confirmed_revision_from_dict(json.loads(row[6]))
    return base_graph, confirmed_graph, confirmation_batch, confirmation_evaluation, confirmation_review, candidate, revision


def action_register_policy(value: ReplicationPolicy) -> dict[str, object]:
    value.validate(); return {"operation": "register_replication_policy", "subject_identity_ref": value.subject_identity_ref, "policy_hash": value.policy_hash, "min_temporal_gap": value.min_temporal_gap, "persistent_drift_epochs": value.persistent_drift_epochs}


def action_register_target(value: ReplicationTargetReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "register_replication_target", "target_hash": value.target_hash, "confirmed_revision_hash": value.confirmed_revision_hash, "confirmed_graph_hash": value.confirmed_graph_hash, "candidate_hash": value.candidate_hash}


def action_seal_batch(value: ReplicationBatch) -> dict[str, object]:
    value.validate(); return {"operation": "seal_replication_batch", "target_hash": value.target_hash, "batch_hash": value.batch_hash, "generation": value.generation, "mode": value.mode, "source_ref": value.source_ref, "environment_ref": value.environment_ref}


def action_evaluate(value: ReplicationEvaluationReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "evaluate_replication", "target_hash": value.target_hash, "batch_hash": value.batch_hash, "evaluation_hash": value.evaluation_hash, "status": value.status, "drift_kind": value.drift_kind}


def action_review(value: ReplicationReviewReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "record_replication_review", "evaluation_hash": value.evaluation_hash, "review_hash": value.review_hash, "decision": value.decision}


def action_snapshot(value: ReplicationSeriesSnapshot) -> dict[str, object]:
    value.validate(); return {"operation": "finalize_replication_snapshot", "target_hash": value.target_hash, "snapshot_hash": value.snapshot_hash, "replication_count": value.replication_count, "signal": value.signal}


def _register_policy(conn, payload, *, grant, proof, enforcement):
    subject = str(payload["subject_identity_ref"])
    policy = make_replication_policy(
        policy_ref=str(payload["policy_ref"]), subject_identity_ref=subject,
        min_replication_samples=int(payload.get("min_replication_samples", 4)), min_temporal_gap=int(payload.get("min_temporal_gap", 1)),
        min_regularized_improvement_ppm=int(payload.get("min_regularized_improvement_ppm", 0)),
        max_proposed_brier_degradation_ppm=int(payload.get("max_proposed_brier_degradation_ppm", 100_000)),
        persistent_drift_epochs=int(payload.get("persistent_drift_epochs", 2)), registered_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_register_policy(policy), required_role=ROLE_REPLICATION_POLICY_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT policy_json FROM replication_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = policy_from_dict(json.loads(row[0]))
        if current == policy: return current
        raise ValueError("replication policy is immutable once registered")
    conn.execute("INSERT INTO replication_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (subject, policy.policy_ref, json.dumps(policy_to_dict(policy), sort_keys=True, separators=(",", ":"))))
    return policy


def _register_target(conn, payload, *, grant, proof, enforcement):
    revision_hash = str(payload["confirmed_revision_hash"])
    base_graph, confirmed_graph, confirmation_batch, confirmation_evaluation, confirmation_review, candidate, revision = _confirmed_bundle(conn, revision_hash)
    del base_graph
    policy = _policy(conn, candidate.subject_identity_ref)
    if confirmed_graph.graph_hash != _graph(conn, candidate.subject_identity_ref).graph_hash:
        raise ValueError("confirmed graph revision is no longer current")
    target = make_replication_target(
        target_ref=str(payload["target_ref"]), confirmed_revision=revision, confirmation_evaluation=confirmation_evaluation,
        confirmation_review=confirmation_review, confirmation_batch=confirmation_batch, candidate=candidate, confirmed_graph=confirmed_graph,
        registered_at=enforcement.now,
    )
    if policy.subject_identity_ref != target.subject_identity_ref:
        raise ValueError("replication target/policy subject mismatch")
    _enforce(grant, proof, action=action_register_target(target), required_role=ROLE_REPLICATION_TARGET_KEEPER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT target_json FROM replication_target WHERE confirmed_revision_hash=?", (revision_hash,)).fetchone()
    if row is not None:
        current = target_from_dict(json.loads(row[0]))
        if current == target: return current
        raise ValueError("confirmed revision already has an immutable replication target")
    conn.execute("INSERT INTO replication_target(target_hash,target_ref,subject_identity_ref,pair_key,confirmed_revision_hash,target_json) VALUES(?,?,?,?,?,?)", (target.target_hash, target.target_ref, target.subject_identity_ref, target.pair_key, revision_hash, json.dumps(target_to_dict(target), sort_keys=True, separators=(",", ":"))))
    return target


def _seal_batch(conn, payload, *, grant, proof, enforcement):
    target = _target(conn, str(payload["target_hash"])); policy = _policy(conn, target.subject_identity_ref)
    _, confirmed_graph, _, _, _, _, _ = _confirmed_bundle(conn, target.confirmed_revision_hash)
    if _graph(conn, target.subject_identity_ref).graph_hash != confirmed_graph.graph_hash:
        raise ValueError("replication target is no longer the current graph")
    prior = _prior_batches(conn, target.target_hash)
    previous = None if not prior else prior[-1]
    samples = tuple(pair_from_dict(_mapping(item, "sample")) for item in payload.get("samples", []))
    batch = make_replication_batch(
        batch_ref=str(payload["batch_ref"]), target=target, policy=policy, mode=str(payload["mode"]), source_ref=str(payload["source_ref"]),
        environment_ref=str(payload["environment_ref"]), samples=samples, collected_from=int(payload["collected_from"]), collected_to=int(payload["collected_to"]),
        generation=len(prior), previous_batch=previous, batch_keeper_ref=grant.subject_ref, sealed_at=enforcement.now,
    )
    assert_replication_freshness(batch=batch, search_samples=_pair_samples(conn, target.pair_key), confirmation_batches=_confirmation_batches(conn, target.subject_identity_ref, target.pair_key), prior_replication_batches=prior)
    _enforce(grant, proof, action=action_seal_batch(batch), required_role=ROLE_REPLICATION_BATCH_KEEPER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT batch_json FROM replication_batch WHERE batch_ref=?", (batch.batch_ref,)).fetchone()
    if row is not None:
        current = batch_from_dict(json.loads(row[0]))
        if current == batch: return current
        raise ValueError("replication batch_ref is immutable")
    conn.execute("INSERT INTO replication_batch(batch_hash,batch_ref,target_hash,generation,batch_json,samples_json) VALUES(?,?,?,?,?,?)", (batch.batch_hash,batch.batch_ref,target.target_hash,batch.generation,json.dumps(batch_to_dict(batch), sort_keys=True, separators=(",", ":")),json.dumps([pair_to_dict(item) for item in samples], sort_keys=True, separators=(",", ":"))))
    return batch


def _evaluate(conn, payload, *, grant, proof, enforcement):
    batch, samples = _batch(conn, str(payload["batch_hash"])); target = _target(conn, batch.target_hash); policy = _policy(conn, target.subject_identity_ref)
    base_graph, confirmed_graph, _, _, _, candidate, _ = _confirmed_bundle(conn, target.confirmed_revision_hash)
    if _graph(conn, target.subject_identity_ref).graph_hash != confirmed_graph.graph_hash:
        raise ValueError("historical replication target no longer represents current model")
    all_batches = _prior_batches(conn, target.target_hash)
    prior = tuple(item for item in all_batches if item.generation < batch.generation)
    assert_replication_freshness(batch=batch, search_samples=_pair_samples(conn, target.pair_key), confirmation_batches=_confirmation_batches(conn, target.subject_identity_ref, target.pair_key), prior_replication_batches=prior)
    cases, evaluation = evaluate_replication(
        target=target, batch=batch, replication_samples=samples, search_samples=_pair_samples(conn, target.pair_key), candidate=candidate,
        base_graph=base_graph, confirmed_graph=confirmed_graph, structural_policy=structural_policy(conn, target.subject_identity_ref), replication_policy=policy,
        evaluator_ref=grant.subject_ref, evaluated_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_evaluate(evaluation), required_role=ROLE_REPLICATION_EVALUATOR, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT evaluation_json FROM replication_evaluation WHERE batch_hash=?", (batch.batch_hash,)).fetchone()
    if row is not None:
        current = evaluation_from_dict(json.loads(row[0]))
        if current == evaluation: return cases, current
        raise ValueError("replication batch evaluation is immutable")
    conn.execute("INSERT INTO replication_evaluation(evaluation_hash,batch_hash,target_hash,evaluation_json,cases_json) VALUES(?,?,?,?,?)", (evaluation.evaluation_hash,batch.batch_hash,target.target_hash,json.dumps(evaluation_to_dict(evaluation), sort_keys=True, separators=(",", ":")),json.dumps([asdict(item) for item in cases], sort_keys=True, separators=(",", ":"))))
    return cases, evaluation


def _record_review(conn, payload, *, grant, proof, enforcement):
    evaluation = _evaluation(conn, str(payload["evaluation_hash"])); target = _target(conn, evaluation.target_hash)
    review = review_replication(evaluation=evaluation, decision=str(payload["decision"]), rationale_ref=str(payload["rationale_ref"]), reviewer_ref=grant.subject_ref, reviewed_at=enforcement.now)
    _enforce(grant, proof, action=action_review(review), required_role=ROLE_REPLICATION_REVIEWER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT review_json FROM replication_review WHERE evaluation_hash=?", (evaluation.evaluation_hash,)).fetchone()
    if row is not None:
        current = review_from_dict(json.loads(row[0]))
        if current == review: return current
        raise ValueError("replication review is immutable")
    conn.execute("INSERT INTO replication_review(review_hash,evaluation_hash,target_hash,review_json) VALUES(?,?,?,?)", (review.review_hash,evaluation.evaluation_hash,target.target_hash,json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":"))))
    return review


def _finalize_snapshot(conn, payload, *, grant, proof, enforcement):
    target = _target(conn, str(payload["target_hash"])); policy = _policy(conn, target.subject_identity_ref)
    eval_rows = conn.execute("SELECT evaluation_json FROM replication_evaluation WHERE target_hash=? ORDER BY evaluation_hash", (target.target_hash,)).fetchall()
    evaluations = tuple(evaluation_from_dict(json.loads(row[0])) for row in eval_rows)
    reviews = []
    for evaluation in evaluations:
        row = conn.execute("SELECT review_json FROM replication_review WHERE evaluation_hash=?", (evaluation.evaluation_hash,)).fetchone()
        if row is None: raise ValueError("replication snapshot requires every evaluation to be reviewed")
        reviews.append(review_from_dict(json.loads(row[0])))
    snapshot = summarize_replication_series(evaluations=evaluations, reviews=tuple(reviews), policy=policy, measured_at=enforcement.now)
    _enforce(grant, proof, action=action_snapshot(snapshot), required_role=ROLE_REPLICATION_MONITOR_KEEPER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT snapshot_json FROM replication_snapshot WHERE target_hash=? AND replication_count=?", (target.target_hash,snapshot.replication_count)).fetchone()
    if row is not None:
        current_data = json.loads(row[0])
        if current_data.get("snapshot_hash") == snapshot.snapshot_hash: return snapshot
        raise ValueError("replication snapshot count is immutable")
    conn.execute("INSERT INTO replication_snapshot(snapshot_hash,target_hash,replication_count,snapshot_json) VALUES(?,?,?,?)", (snapshot.snapshot_hash,target.target_hash,snapshot.replication_count,json.dumps(snapshot_to_dict(snapshot), sort_keys=True, separators=(",", ":"))))
    return snapshot


def _state(conn: sqlite3.Connection) -> dict[str, object]:
    policies = conn.execute("SELECT policy_json FROM replication_policy ORDER BY subject_identity_ref").fetchall()
    targets = conn.execute("SELECT target_json FROM replication_target ORDER BY target_hash").fetchall()
    batches = conn.execute("SELECT batch_json FROM replication_batch ORDER BY target_hash,generation").fetchall()
    evaluations = conn.execute("SELECT evaluation_hash FROM replication_evaluation ORDER BY evaluation_hash").fetchall()
    reviews = conn.execute("SELECT review_hash FROM replication_review ORDER BY review_hash").fetchall()
    snapshots = conn.execute("SELECT snapshot_hash FROM replication_snapshot ORDER BY snapshot_hash").fetchall()
    return {
        "policies": [policy_to_dict(policy_from_dict(json.loads(row[0]))) for row in policies],
        "targets": [target_to_dict(target_from_dict(json.loads(row[0]))) for row in targets],
        "batches": [batch_to_dict(batch_from_dict(json.loads(row[0]))) for row in batches],
        "evaluation_hashes": [str(row[0]) for row in evaluations],
        "review_hashes": [str(row[0]) for row in reviews],
        "snapshot_hashes": [str(row[0]) for row in snapshots],
    }


def execute_replication_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != REPLICATION_PROTOCOL: raise ValueError("unsupported replication protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id: raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in REPLICATION_OPERATIONS: raise ValueError("unsupported replication operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_replication_state": return {"protocol": REPLICATION_PROTOCOL, "request_id": request_id, "ok": True, **_state(conn)}
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant")); proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_replication_policy":
            value = _register_policy(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"ok":True,"policy":policy_to_dict(value)}
        if operation == "register_replication_target":
            value = _register_target(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"ok":True,"target":target_to_dict(value)}
        if operation == "seal_replication_batch":
            value = _seal_batch(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"ok":True,"batch":batch_to_dict(value)}
        if operation == "evaluate_replication":
            cases,value = _evaluate(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"ok":True,"evaluation":evaluation_to_dict(value),"case_hashes":[item.case_hash for item in cases]}
        if operation == "record_replication_review":
            value = _record_review(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"ok":True,"review":review_to_dict(value)}
        value = _finalize_snapshot(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
        return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"ok":True,"snapshot":snapshot_to_dict(value)}
    except Exception:
        if conn.in_transaction: conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
