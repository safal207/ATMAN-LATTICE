from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.protected_confirmation import (
    ConfirmationCase,
    ConfirmationEvaluationReceipt,
    ConfirmationExposureReceipt,
    ConfirmationReviewReceipt,
    ConfirmedGraphRevisionReceipt,
    ProtectedConfirmationBatch,
    ProtectedConfirmationPolicy,
    apply_confirmed_selection,
    assert_confirmation_freshness,
    authorize_confirmation_exposure,
    evaluate_confirmation,
    make_confirmation_batch,
    make_confirmation_policy,
    review_confirmation,
)
from model.runtime_calibration import pair_from_dict, pair_to_dict
from model.runtime_dependency_graph import _graph, _pair_samples, graph_to_dict
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_search_budget import (
    _candidate,
    _connect as search_connect,
    _current_search_state,
    _evaluation_bundle,
    _reservation,
    _review as search_review,
    _selection as search_selection,
    evaluation_to_dict as search_evaluation_to_dict,
    reservation_to_dict as search_reservation_to_dict,
    review_to_dict as search_review_to_dict,
    selection_to_dict as search_selection_to_dict,
)
from model.runtime_structural_validation import _policy as structural_policy, candidate_to_dict, validation_to_dict
from model.runtime_verification import verification_scope
from model.search_budget import select_search_budget_candidate

CONFIRM_PROTOCOL = "ATMAN-CONFIRM/1.17"
CONFIRM_OPERATIONS = {
    "register_confirmation_policy",
    "seal_confirmation_batch",
    "authorize_confirmation_exposure",
    "evaluate_confirmation",
    "record_confirmation_review",
    "apply_confirmed_structural_selection",
    "get_confirmation_state",
}

ROLE_CONFIRM_POLICY_KEEPER = "CONFIRMATION_POLICY_KEEPER"
ROLE_CONFIRM_BATCH_KEEPER = "CONFIRMATION_BATCH_KEEPER"
ROLE_CONFIRM_EXPOSURE_KEEPER = "CONFIRMATION_EXPOSURE_KEEPER"
ROLE_CONFIRM_EVALUATOR = "CONFIRMATION_EVALUATOR"
ROLE_CONFIRM_REVIEWER = "CONFIRMATION_REVIEWER"
ROLE_CONFIRMED_APPLIER = "CONFIRMED_STRUCTURAL_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def policy_to_dict(value: ProtectedConfirmationPolicy) -> dict[str, object]:
    value.validate(); return asdict(value)


def policy_from_dict(data: Mapping[str, object]) -> ProtectedConfirmationPolicy:
    result = ProtectedConfirmationPolicy(
        policy_ref=str(data["policy_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        min_confirmation_samples=int(data["min_confirmation_samples"]),
        min_regularized_improvement_ppm=int(data["min_regularized_improvement_ppm"]),
        registered_at=int(data["registered_at"]),
        policy_hash=str(data["policy_hash"]),
    )
    result.validate(); return result


def batch_to_dict(value: ProtectedConfirmationBatch) -> dict[str, object]:
    value.validate(); data = asdict(value)
    data["sample_hashes"] = list(value.sample_hashes); data["resolution_hashes"] = list(value.resolution_hashes); data["evidence_hashes"] = list(value.evidence_hashes)
    return data


def batch_from_dict(data: Mapping[str, object]) -> ProtectedConfirmationBatch:
    result = ProtectedConfirmationBatch(
        batch_ref=str(data["batch_ref"]), subject_identity_ref=str(data["subject_identity_ref"]), pair_key=str(data["pair_key"]), source_ref=str(data["source_ref"]),
        sample_hashes=tuple(str(v) for v in data.get("sample_hashes", [])), resolution_hashes=tuple(str(v) for v in data.get("resolution_hashes", [])), evidence_hashes=tuple(str(v) for v in data.get("evidence_hashes", [])),
        sample_count=int(data["sample_count"]), batch_keeper_ref=str(data["batch_keeper_ref"]), sealed_at=int(data["sealed_at"]), batch_hash=str(data["batch_hash"]),
    )
    result.validate(); return result


def exposure_to_dict(value: ConfirmationExposureReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def exposure_from_dict(data: Mapping[str, object]) -> ConfirmationExposureReceipt:
    result = ConfirmationExposureReceipt(
        selection_hash=str(data["selection_hash"]), candidate_hash=str(data["candidate_hash"]), search_review_hash=str(data["search_review_hash"]), batch_hash=str(data["batch_hash"]), confirmation_policy_hash=str(data["confirmation_policy_hash"]), search_history_hash=str(data["search_history_hash"]), base_graph_hash=str(data["base_graph_hash"]), proposer_ref=str(data["proposer_ref"]), selector_ref=str(data["selector_ref"]), batch_keeper_ref=str(data["batch_keeper_ref"]), exposure_keeper_ref=str(data["exposure_keeper_ref"]), authorized_at=int(data["authorized_at"]), exposure_hash=str(data["exposure_hash"]),
    )
    result.validate(); return result


def confirmation_case_to_dict(value: ConfirmationCase) -> dict[str, object]:
    value.validate(); return asdict(value)


def evaluation_to_dict(value: ConfirmationEvaluationReceipt) -> dict[str, object]:
    value.validate(); data = asdict(value); data["case_hashes"] = list(value.case_hashes); return data


def evaluation_from_dict(data: Mapping[str, object]) -> ConfirmationEvaluationReceipt:
    result = ConfirmationEvaluationReceipt(
        selection_hash=str(data["selection_hash"]), candidate_hash=str(data["candidate_hash"]), batch_hash=str(data["batch_hash"]), exposure_hash=str(data["exposure_hash"]), confirmation_policy_hash=str(data["confirmation_policy_hash"]), case_hashes=tuple(str(v) for v in data.get("case_hashes", [])), evaluated_case_count=int(data["evaluated_case_count"]), min_confirmation_samples=int(data["min_confirmation_samples"]),
        base_mean_brier_ppm=None if data.get("base_mean_brier_ppm") is None else int(data["base_mean_brier_ppm"]), proposed_mean_brier_ppm=None if data.get("proposed_mean_brier_ppm") is None else int(data["proposed_mean_brier_ppm"]), raw_improvement_ppm=None if data.get("raw_improvement_ppm") is None else int(data["raw_improvement_ppm"]), base_regularized_brier_ppm=None if data.get("base_regularized_brier_ppm") is None else int(data["base_regularized_brier_ppm"]), proposed_regularized_brier_ppm=None if data.get("proposed_regularized_brier_ppm") is None else int(data["proposed_regularized_brier_ppm"]), regularized_improvement_ppm=None if data.get("regularized_improvement_ppm") is None else int(data["regularized_improvement_ppm"]), required_min_regularized_improvement_ppm=int(data["required_min_regularized_improvement_ppm"]), status=str(data["status"]), proposer_ref=str(data["proposer_ref"]), selector_ref=str(data["selector_ref"]), batch_keeper_ref=str(data["batch_keeper_ref"]), exposure_keeper_ref=str(data["exposure_keeper_ref"]), evaluator_ref=str(data["evaluator_ref"]), evaluated_at=int(data["evaluated_at"]), evaluation_hash=str(data["evaluation_hash"]),
    )
    result.validate(); return result


def review_to_dict(value: ConfirmationReviewReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> ConfirmationReviewReceipt:
    result = ConfirmationReviewReceipt(
        evaluation_hash=str(data["evaluation_hash"]), selection_hash=str(data["selection_hash"]), candidate_hash=str(data["candidate_hash"]), status=str(data["status"]), decision=str(data["decision"]), rationale_ref=str(data["rationale_ref"]), proposer_ref=str(data["proposer_ref"]), selector_ref=str(data["selector_ref"]), evaluator_ref=str(data["evaluator_ref"]), reviewer_ref=str(data["reviewer_ref"]), reviewed_at=int(data["reviewed_at"]), review_hash=str(data["review_hash"]),
    )
    result.validate(); return result


def revision_to_dict(value: ConfirmedGraphRevisionReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = search_connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS protected_confirmation_policy (subject_identity_ref TEXT PRIMARY KEY, policy_ref TEXT NOT NULL UNIQUE, policy_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS protected_confirmation_batch (batch_hash TEXT PRIMARY KEY, batch_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, pair_key TEXT NOT NULL, batch_json TEXT NOT NULL, samples_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS protected_confirmation_exposure (exposure_hash TEXT PRIMARY KEY, selection_hash TEXT NOT NULL UNIQUE, batch_hash TEXT NOT NULL UNIQUE, exposure_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS protected_confirmation_evaluation (evaluation_hash TEXT PRIMARY KEY, exposure_hash TEXT NOT NULL UNIQUE, evaluation_json TEXT NOT NULL, cases_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS protected_confirmation_review (review_hash TEXT PRIMARY KEY, evaluation_hash TEXT NOT NULL UNIQUE, review_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS protected_confirmation_revision_history (revision_hash TEXT PRIMARY KEY, selection_hash TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, base_graph_hash TEXT NOT NULL, new_graph_hash TEXT NOT NULL, base_graph_json TEXT NOT NULL, new_graph_json TEXT NOT NULL, batch_json TEXT NOT NULL, exposure_json TEXT NOT NULL, confirmation_evaluation_json TEXT NOT NULL, confirmation_review_json TEXT NOT NULL, search_selection_json TEXT NOT NULL, search_review_json TEXT NOT NULL, candidate_json TEXT NOT NULL, search_reservation_json TEXT NOT NULL, search_underlying_validation_json TEXT NOT NULL, search_evaluation_json TEXT NOT NULL, revision_json TEXT NOT NULL)""")
    return conn


def _enforce(grant: AuthorityGrant, proof: AuthorityProof, *, action: object, required_role: str, required_scope: str, enforcement: EnforcementContext) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(grant, proof, action=action, trusted_issuer_keys=enforcement.trusted_issuer_keys, current_policy_generation=enforcement.policy_generation, now=enforcement.now)
    failures = list(limitations)
    if proof.role != required_role: failures.append("required_role_mismatch")
    if proof.scope != required_scope: failures.append("required_scope_mismatch")
    if not valid or failures: raise PermissionError("confirmation authority failed: " + ",".join(dict.fromkeys(failures)))


def _policy(conn: sqlite3.Connection, subject: str) -> ProtectedConfirmationPolicy:
    row = conn.execute("SELECT policy_json FROM protected_confirmation_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is None: raise ValueError("protected confirmation policy is not registered")
    return policy_from_dict(json.loads(row[0]))


def _batch(conn: sqlite3.Connection, batch_hash: str) -> tuple[ProtectedConfirmationBatch, tuple[object, ...]]:
    row = conn.execute("SELECT batch_json,samples_json FROM protected_confirmation_batch WHERE batch_hash=?", (batch_hash,)).fetchone()
    if row is None: raise ValueError("unknown protected confirmation batch")
    return batch_from_dict(json.loads(row[0])), tuple(pair_from_dict(item) for item in json.loads(row[1]))


def _prior_batches(conn: sqlite3.Connection, subject: str, pair_key: str) -> tuple[ProtectedConfirmationBatch, ...]:
    rows = conn.execute("SELECT batch_json FROM protected_confirmation_batch WHERE subject_identity_ref=? AND pair_key=? ORDER BY batch_hash", (subject, pair_key)).fetchall()
    return tuple(batch_from_dict(json.loads(row[0])) for row in rows)


def _exposure(conn: sqlite3.Connection, exposure_hash: str) -> ConfirmationExposureReceipt:
    row = conn.execute("SELECT exposure_json FROM protected_confirmation_exposure WHERE exposure_hash=?", (exposure_hash,)).fetchone()
    if row is None: raise ValueError("unknown confirmation exposure")
    return exposure_from_dict(json.loads(row[0]))


def _prior_exposures(conn: sqlite3.Connection) -> tuple[ConfirmationExposureReceipt, ...]:
    rows = conn.execute("SELECT exposure_json FROM protected_confirmation_exposure ORDER BY exposure_hash").fetchall()
    return tuple(exposure_from_dict(json.loads(row[0])) for row in rows)


def _evaluation(conn: sqlite3.Connection, evaluation_hash: str) -> ConfirmationEvaluationReceipt:
    row = conn.execute("SELECT evaluation_json FROM protected_confirmation_evaluation WHERE evaluation_hash=?", (evaluation_hash,)).fetchone()
    if row is None: raise ValueError("unknown confirmation evaluation")
    return evaluation_from_dict(json.loads(row[0]))


def _review(conn: sqlite3.Connection, evaluation_hash: str) -> ConfirmationReviewReceipt:
    row = conn.execute("SELECT review_json FROM protected_confirmation_review WHERE evaluation_hash=?", (evaluation_hash,)).fetchone()
    if row is None: raise ValueError("confirmation review is not recorded")
    return review_from_dict(json.loads(row[0]))


def _fresh_search_selection(conn: sqlite3.Connection, selection_hash: str):
    selection = search_selection(conn, selection_hash)
    _, search_policy, current_graph, samples, reservations, candidates, evaluations = _current_search_state(conn, subject=selection.subject_identity_ref, pair_key=selection.pair_key)
    fresh = select_search_budget_candidate(selection_ref=selection.selection_ref, current_candidates=candidates, current_evaluations=evaluations, all_family_reservations=reservations, search_policy=search_policy, selector_ref=selection.selector_ref, selected_at=selection.selected_at)
    if fresh != selection:
        raise ValueError("stale search selection before protected confirmation")
    if selection.status != "SELECTED" or selection.selected_candidate_hash is None:
        raise ValueError("protected confirmation requires selected search winner")
    return selection, current_graph, tuple(samples)


def action_register_policy(value: ProtectedConfirmationPolicy) -> dict[str, object]:
    value.validate(); return {"operation": "register_confirmation_policy", "subject_identity_ref": value.subject_identity_ref, "policy_hash": value.policy_hash, "min_confirmation_samples": value.min_confirmation_samples, "min_regularized_improvement_ppm": value.min_regularized_improvement_ppm}


def action_seal_batch(value: ProtectedConfirmationBatch) -> dict[str, object]:
    value.validate(); return {"operation": "seal_confirmation_batch", "batch_hash": value.batch_hash, "subject_identity_ref": value.subject_identity_ref, "pair_key": value.pair_key, "sample_hashes": list(value.sample_hashes), "source_ref": value.source_ref}


def action_authorize_exposure(value: ConfirmationExposureReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "authorize_confirmation_exposure", "selection_hash": value.selection_hash, "candidate_hash": value.candidate_hash, "batch_hash": value.batch_hash, "exposure_hash": value.exposure_hash}


def action_evaluate(value: ConfirmationEvaluationReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "evaluate_confirmation", "selection_hash": value.selection_hash, "batch_hash": value.batch_hash, "exposure_hash": value.exposure_hash, "evaluation_hash": value.evaluation_hash, "status": value.status, "regularized_improvement_ppm": value.regularized_improvement_ppm}


def action_review(value: ConfirmationReviewReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "record_confirmation_review", "evaluation_hash": value.evaluation_hash, "review_hash": value.review_hash, "decision": value.decision}


def action_apply(value: ConfirmedGraphRevisionReceipt) -> dict[str, object]:
    value.validate(); return {"operation": "apply_confirmed_structural_selection", "selection_hash": value.selection_hash, "confirmation_evaluation_hash": value.confirmation_evaluation_hash, "confirmation_review_hash": value.confirmation_review_hash, "base_graph_hash": value.base_graph_hash, "new_graph_hash": value.new_graph_hash, "revision_hash": value.revision_hash}


def _register_policy(conn, payload, *, grant, proof, enforcement):
    subject = str(payload["subject_identity_ref"])
    policy = make_confirmation_policy(policy_ref=str(payload["policy_ref"]), subject_identity_ref=subject, min_confirmation_samples=int(payload.get("min_confirmation_samples", 4)), min_regularized_improvement_ppm=int(payload.get("min_regularized_improvement_ppm", 0)), registered_at=enforcement.now)
    _enforce(grant, proof, action=action_register_policy(policy), required_role=ROLE_CONFIRM_POLICY_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT policy_json FROM protected_confirmation_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = policy_from_dict(json.loads(row[0]))
        if current == policy: return current
        raise ValueError("confirmation policy is immutable once registered")
    conn.execute("INSERT INTO protected_confirmation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (subject, policy.policy_ref, json.dumps(policy_to_dict(policy), sort_keys=True, separators=(",", ":"))))
    return policy


def _seal_batch(conn, payload, *, grant, proof, enforcement):
    subject = str(payload["subject_identity_ref"]); pair_key = str(payload["pair_key"])
    _policy(conn, subject)
    samples = tuple(pair_from_dict(_mapping(item, "confirmation sample")) for item in payload.get("samples", []))
    batch = make_confirmation_batch(batch_ref=str(payload["batch_ref"]), subject_identity_ref=subject, pair_key=pair_key, source_ref=str(payload["source_ref"]), samples=samples, batch_keeper_ref=grant.subject_ref, sealed_at=enforcement.now)
    search_samples = tuple(_pair_samples(conn, pair_key)); prior = _prior_batches(conn, subject, pair_key)
    assert_confirmation_freshness(batch=batch, search_samples=search_samples, prior_batches=prior)
    _enforce(grant, proof, action=action_seal_batch(batch), required_role=ROLE_CONFIRM_BATCH_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT batch_json FROM protected_confirmation_batch WHERE batch_ref=?", (batch.batch_ref,)).fetchone()
    if row is not None:
        current = batch_from_dict(json.loads(row[0]))
        if current == batch: return current
        raise ValueError("confirmation batch_ref is immutable once sealed")
    conn.execute("INSERT INTO protected_confirmation_batch(batch_hash,batch_ref,subject_identity_ref,pair_key,batch_json,samples_json) VALUES(?,?,?,?,?,?)", (batch.batch_hash, batch.batch_ref, subject, pair_key, json.dumps(batch_to_dict(batch), sort_keys=True, separators=(",", ":")), json.dumps([pair_to_dict(item) for item in samples], sort_keys=True, separators=(",", ":"))))
    return batch


def _authorize_exposure(conn, payload, *, grant, proof, enforcement):
    selection, _, search_samples = _fresh_search_selection(conn, str(payload["selection_hash"]))
    candidate = _candidate(conn, selection.selected_candidate_hash)
    review = search_review(conn, selection.selection_hash)
    batch, _ = _batch(conn, str(payload["batch_hash"]))
    policy = _policy(conn, selection.subject_identity_ref)
    assert_confirmation_freshness(batch=batch, search_samples=search_samples, prior_batches=tuple(item for item in _prior_batches(conn, batch.subject_identity_ref, batch.pair_key) if item.batch_hash != batch.batch_hash))
    exposure = authorize_confirmation_exposure(selection=selection, search_review=review, candidate=candidate, batch=batch, policy=policy, prior_exposures=_prior_exposures(conn), exposure_keeper_ref=grant.subject_ref, authorized_at=enforcement.now)
    _enforce(grant, proof, action=action_authorize_exposure(exposure), required_role=ROLE_CONFIRM_EXPOSURE_KEEPER, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    conn.execute("INSERT INTO protected_confirmation_exposure(exposure_hash,selection_hash,batch_hash,exposure_json) VALUES(?,?,?,?)", (exposure.exposure_hash, exposure.selection_hash, exposure.batch_hash, json.dumps(exposure_to_dict(exposure), sort_keys=True, separators=(",", ":"))))
    return exposure


def _evaluate_confirmation(conn, payload, *, grant, proof, enforcement):
    exposure = _exposure(conn, str(payload["exposure_hash"]))
    selection, current_graph, search_samples = _fresh_search_selection(conn, exposure.selection_hash)
    if exposure.selection_hash != selection.selection_hash or exposure.base_graph_hash != current_graph.graph_hash or exposure.search_history_hash != selection.history_hash:
        raise ValueError("stale confirmation exposure")
    candidate = _candidate(conn, exposure.candidate_hash); batch, confirmation_samples = _batch(conn, exposure.batch_hash)
    assert_confirmation_freshness(batch=batch, search_samples=search_samples, prior_batches=tuple(item for item in _prior_batches(conn, batch.subject_identity_ref, batch.pair_key) if item.batch_hash != batch.batch_hash))
    cases, evaluation = evaluate_confirmation(selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=confirmation_samples, search_samples=search_samples, current_graph=current_graph, structural_policy=structural_policy(conn, selection.subject_identity_ref), confirmation_policy=_policy(conn, selection.subject_identity_ref), evaluator_ref=grant.subject_ref, evaluated_at=enforcement.now)
    _enforce(grant, proof, action=action_evaluate(evaluation), required_role=ROLE_CONFIRM_EVALUATOR, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT evaluation_json FROM protected_confirmation_evaluation WHERE exposure_hash=?", (exposure.exposure_hash,)).fetchone()
    if row is not None:
        current = evaluation_from_dict(json.loads(row[0]))
        if current == evaluation: return cases, current
        raise ValueError("confirmation evaluation is immutable once recorded")
    conn.execute("INSERT INTO protected_confirmation_evaluation(evaluation_hash,exposure_hash,evaluation_json,cases_json) VALUES(?,?,?,?)", (evaluation.evaluation_hash, exposure.exposure_hash, json.dumps(evaluation_to_dict(evaluation), sort_keys=True, separators=(",", ":")), json.dumps([confirmation_case_to_dict(item) for item in cases], sort_keys=True, separators=(",", ":"))))
    return cases, evaluation


def _record_review(conn, payload, *, grant, proof, enforcement):
    evaluation = _evaluation(conn, str(payload["evaluation_hash"]))
    review = review_confirmation(evaluation=evaluation, decision=str(payload["decision"]), rationale_ref=str(payload["rationale_ref"]), reviewer_ref=grant.subject_ref, reviewed_at=enforcement.now)
    _enforce(grant, proof, action=action_review(review), required_role=ROLE_CONFIRM_REVIEWER, required_scope=verification_scope(search_selection(conn, evaluation.selection_hash).subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT review_json FROM protected_confirmation_review WHERE evaluation_hash=?", (evaluation.evaluation_hash,)).fetchone()
    if row is not None:
        current = review_from_dict(json.loads(row[0]))
        if current == review: return current
        raise ValueError("confirmation review is immutable once recorded")
    conn.execute("INSERT INTO protected_confirmation_review(review_hash,evaluation_hash,review_json) VALUES(?,?,?)", (review.review_hash, evaluation.evaluation_hash, json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":"))))
    return review


def _apply(conn, payload, *, grant, proof, enforcement):
    evaluation = _evaluation(conn, str(payload["evaluation_hash"])); review = _review(conn, evaluation.evaluation_hash); exposure = _exposure(conn, evaluation.exposure_hash)
    selection, current_graph, search_samples = _fresh_search_selection(conn, evaluation.selection_hash)
    candidate = _candidate(conn, evaluation.candidate_hash); batch, confirmation_samples = _batch(conn, evaluation.batch_hash)
    assert_confirmation_freshness(batch=batch, search_samples=search_samples, prior_batches=tuple(item for item in _prior_batches(conn, batch.subject_identity_ref, batch.pair_key) if item.batch_hash != batch.batch_hash))
    fresh_cases, fresh_evaluation = evaluate_confirmation(selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=confirmation_samples, search_samples=search_samples, current_graph=current_graph, structural_policy=structural_policy(conn, selection.subject_identity_ref), confirmation_policy=_policy(conn, selection.subject_identity_ref), evaluator_ref=evaluation.evaluator_ref, evaluated_at=evaluation.evaluated_at)
    if fresh_evaluation != evaluation:
        raise ValueError("stale protected confirmation evaluation")
    reservation = _reservation(conn, candidate.candidate_hash); underlying, search_evaluation = _evaluation_bundle(conn, candidate.candidate_hash); sreview = search_review(conn, selection.selection_hash)
    new_graph, revision = apply_confirmed_selection(current_graph=current_graph, candidate=candidate, reservation=reservation, underlying_validation=underlying, search_evaluation=search_evaluation, search_selection=selection, search_review=sreview, exposure=exposure, confirmation_evaluation=evaluation, confirmation_review=review, applier_ref=grant.subject_ref, applied_at=enforcement.now)
    _enforce(grant, proof, action=action_apply(revision), required_role=ROLE_CONFIRMED_APPLIER, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    if conn.execute("SELECT 1 FROM protected_confirmation_revision_history WHERE selection_hash=?", (selection.selection_hash,)).fetchone() is not None:
        raise ValueError("confirmed structural selection has already been applied")
    base_json = json.dumps(graph_to_dict(current_graph), sort_keys=True, separators=(",", ":")); new_json = json.dumps(graph_to_dict(new_graph), sort_keys=True, separators=(",", ":"))
    conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?", (new_json, selection.subject_identity_ref))
    conn.execute("INSERT INTO protected_confirmation_revision_history(revision_hash,selection_hash,subject_identity_ref,base_graph_hash,new_graph_hash,base_graph_json,new_graph_json,batch_json,exposure_json,confirmation_evaluation_json,confirmation_review_json,search_selection_json,search_review_json,candidate_json,search_reservation_json,search_underlying_validation_json,search_evaluation_json,revision_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (revision.revision_hash, selection.selection_hash, selection.subject_identity_ref, current_graph.graph_hash, new_graph.graph_hash, base_json, new_json, json.dumps(batch_to_dict(batch), sort_keys=True, separators=(",", ":")), json.dumps(exposure_to_dict(exposure), sort_keys=True, separators=(",", ":")), json.dumps(evaluation_to_dict(evaluation), sort_keys=True, separators=(",", ":")), json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":")), json.dumps(search_selection_to_dict(selection), sort_keys=True, separators=(",", ":")), json.dumps(search_review_to_dict(sreview), sort_keys=True, separators=(",", ":")), json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":")), json.dumps(search_reservation_to_dict(reservation), sort_keys=True, separators=(",", ":")), json.dumps(validation_to_dict(underlying), sort_keys=True, separators=(",", ":")), json.dumps(search_evaluation_to_dict(search_evaluation), sort_keys=True, separators=(",", ":")), json.dumps(revision_to_dict(revision), sort_keys=True, separators=(",", ":"))))
    return new_graph, revision


def _state(conn):
    return {
        "policies": [policy_to_dict(policy_from_dict(json.loads(row[0]))) for row in conn.execute("SELECT policy_json FROM protected_confirmation_policy ORDER BY subject_identity_ref").fetchall()],
        "batch_hashes": [str(row[0]) for row in conn.execute("SELECT batch_hash FROM protected_confirmation_batch ORDER BY batch_hash").fetchall()],
        "exposure_hashes": [str(row[0]) for row in conn.execute("SELECT exposure_hash FROM protected_confirmation_exposure ORDER BY exposure_hash").fetchall()],
        "evaluation_hashes": [str(row[0]) for row in conn.execute("SELECT evaluation_hash FROM protected_confirmation_evaluation ORDER BY evaluation_hash").fetchall()],
        "review_hashes": [str(row[0]) for row in conn.execute("SELECT review_hash FROM protected_confirmation_review ORDER BY review_hash").fetchall()],
        "revision_hashes": [str(row[0]) for row in conn.execute("SELECT revision_hash FROM protected_confirmation_revision_history ORDER BY revision_hash").fetchall()],
    }


def execute_confirmation_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != CONFIRM_PROTOCOL: raise ValueError("unsupported protected confirmation protocol")
    request_id = str(request.get("request_id", "")); operation = str(request.get("operation", ""))
    if not request_id: raise ValueError("request_id is required")
    if operation not in CONFIRM_OPERATIONS: raise ValueError("unsupported protected confirmation operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if operation == "get_confirmation_state":
            result = _state(conn); conn.commit(); return {"protocol": CONFIRM_PROTOCOL, "request_id": request_id, "ok": True, "state": result}
        grant = authority_grant_from_dict(_mapping(request.get("grant", {}), "grant")); proof = authority_proof_from_dict(_mapping(request.get("proof", {}), "proof"))
        if operation == "register_confirmation_policy":
            value = _register_policy(conn, payload, grant=grant, proof=proof, enforcement=enforcement); response = {"policy": policy_to_dict(value)}
        elif operation == "seal_confirmation_batch":
            value = _seal_batch(conn, payload, grant=grant, proof=proof, enforcement=enforcement); response = {"batch": batch_to_dict(value)}
        elif operation == "authorize_confirmation_exposure":
            value = _authorize_exposure(conn, payload, grant=grant, proof=proof, enforcement=enforcement); response = {"exposure": exposure_to_dict(value)}
        elif operation == "evaluate_confirmation":
            cases, value = _evaluate_confirmation(conn, payload, grant=grant, proof=proof, enforcement=enforcement); response = {"cases": [confirmation_case_to_dict(item) for item in cases], "evaluation": evaluation_to_dict(value)}
        elif operation == "record_confirmation_review":
            value = _record_review(conn, payload, grant=grant, proof=proof, enforcement=enforcement); response = {"review": review_to_dict(value)}
        elif operation == "apply_confirmed_structural_selection":
            new_graph, value = _apply(conn, payload, grant=grant, proof=proof, enforcement=enforcement); response = {"graph": graph_to_dict(new_graph), "revision": revision_to_dict(value)}
        else:
            raise AssertionError("unreachable confirmation operation")
        conn.commit(); return {"protocol": CONFIRM_PROTOCOL, "request_id": request_id, "ok": True, **response}
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
