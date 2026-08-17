from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.dependency_graph_revision import DependencyGraphState
from model.enforcement import EnforcementContext
from model.runtime_dependency_graph import (
    _connect as graph_connect,
    _graph,
    _pair_samples,
    graph_from_dict,
    graph_to_dict,
    proposal_from_dict,
    proposal_to_dict,
    replay_from_dict,
    replay_to_dict,
)
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import verification_scope
from model.structural_validation import (
    HeldOutStructuralCase,
    HeldOutStructuralValidationReceipt,
    StructuralSelectionReceipt,
    StructuralSelectionReviewReceipt,
    StructuralValidationCandidate,
    StructuralValidationPolicy,
    ValidatedDependencyGraphRevisionReceipt,
    apply_validated_structural_selection,
    dependency_history_hash,
    make_structural_validation_candidate,
    make_structural_validation_policy,
    review_structural_selection,
    select_structural_candidate,
    validate_structural_candidate,
)

STRUCTURE_PROTOCOL = "ATMAN-STRUCTURE/1.15"
STRUCTURE_OPERATIONS = {
    "register_structural_validation_policy",
    "register_structural_candidate",
    "record_heldout_validation",
    "finalize_structural_selection",
    "record_structural_selection_review",
    "apply_validated_structural_selection",
    "get_structural_validation_state",
}

ROLE_VALIDATION_POLICY_KEEPER = "STRUCTURAL_VALIDATION_POLICY_KEEPER"
ROLE_STRUCTURAL_CANDIDATE_PROPOSER = "STRUCTURAL_CANDIDATE_PROPOSER"
ROLE_HELDOUT_VALIDATOR = "HELDOUT_STRUCTURAL_VALIDATOR"
ROLE_STRUCTURAL_SELECTOR = "STRUCTURAL_MODEL_SELECTOR"
ROLE_STRUCTURAL_SELECTION_REVIEWER = "STRUCTURAL_SELECTION_REVIEWER"
ROLE_VALIDATED_STRUCTURAL_APPLIER = "VALIDATED_STRUCTURAL_SELECTION_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def policy_to_dict(value: StructuralValidationPolicy) -> dict[str, object]:
    value.validate()
    return asdict(value)


def policy_from_dict(data: Mapping[str, object]) -> StructuralValidationPolicy:
    result = StructuralValidationPolicy(
        policy_ref=str(data["policy_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        evaluation_modulus=int(data["evaluation_modulus"]),
        min_selection_samples=int(data["min_selection_samples"]),
        min_evaluation_samples=int(data["min_evaluation_samples"]),
        dependency_threshold_bps=int(data["dependency_threshold_bps"]),
        edge_penalty_ppm=int(data["edge_penalty_ppm"]),
        registered_at=int(data["registered_at"]),
        policy_hash=str(data["policy_hash"]),
    )
    result.validate()
    return result


def candidate_to_dict(value: StructuralValidationCandidate) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["selection_sample_hashes"] = list(value.selection_sample_hashes)
    data["evaluation_sample_hashes"] = list(value.evaluation_sample_hashes)
    data["proposal"] = proposal_to_dict(value.proposal)
    data["selection_replay"] = replay_to_dict(value.selection_replay)
    return data


def candidate_from_dict(data: Mapping[str, object]) -> StructuralValidationCandidate:
    result = StructuralValidationCandidate(
        candidate_ref=str(data["candidate_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        pair_key=str(data["pair_key"]),
        policy_hash=str(data["policy_hash"]),
        history_hash=str(data["history_hash"]),
        split_hash=str(data["split_hash"]),
        selection_sample_hashes=tuple(str(value) for value in data.get("selection_sample_hashes", [])),
        evaluation_sample_hashes=tuple(str(value) for value in data.get("evaluation_sample_hashes", [])),
        proposal=proposal_from_dict(_mapping(data["proposal"], "proposal")),
        selection_replay=replay_from_dict(_mapping(data["selection_replay"], "selection_replay")),
        proposer_ref=str(data["proposer_ref"]),
        created_at=int(data["created_at"]),
        candidate_hash=str(data["candidate_hash"]),
    )
    result.validate()
    return result


def heldout_case_to_dict(value: HeldOutStructuralCase) -> dict[str, object]:
    value.validate()
    return asdict(value)


def validation_to_dict(value: HeldOutStructuralValidationReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["selection_sample_hashes"] = list(value.selection_sample_hashes)
    data["evaluation_sample_hashes"] = list(value.evaluation_sample_hashes)
    data["case_hashes"] = list(value.case_hashes)
    return data


def validation_from_dict(data: Mapping[str, object]) -> HeldOutStructuralValidationReceipt:
    result = HeldOutStructuralValidationReceipt(
        candidate_hash=str(data["candidate_hash"]),
        proposal_hash=str(data["proposal_hash"]),
        selection_replay_hash=str(data["selection_replay_hash"]),
        policy_hash=str(data["policy_hash"]),
        history_hash=str(data["history_hash"]),
        split_hash=str(data["split_hash"]),
        selection_sample_hashes=tuple(str(value) for value in data.get("selection_sample_hashes", [])),
        evaluation_sample_hashes=tuple(str(value) for value in data.get("evaluation_sample_hashes", [])),
        case_hashes=tuple(str(value) for value in data.get("case_hashes", [])),
        evaluated_case_count=int(data["evaluated_case_count"]),
        min_evaluation_samples=int(data["min_evaluation_samples"]),
        base_mean_brier_ppm=None if data.get("base_mean_brier_ppm") is None else int(data["base_mean_brier_ppm"]),
        proposed_mean_brier_ppm=None if data.get("proposed_mean_brier_ppm") is None else int(data["proposed_mean_brier_ppm"]),
        raw_improvement_ppm=None if data.get("raw_improvement_ppm") is None else int(data["raw_improvement_ppm"]),
        base_edge_count=int(data["base_edge_count"]),
        proposed_edge_count=int(data["proposed_edge_count"]),
        edge_penalty_ppm=int(data["edge_penalty_ppm"]),
        base_regularized_brier_ppm=None if data.get("base_regularized_brier_ppm") is None else int(data["base_regularized_brier_ppm"]),
        proposed_regularized_brier_ppm=None if data.get("proposed_regularized_brier_ppm") is None else int(data["proposed_regularized_brier_ppm"]),
        regularized_improvement_ppm=None if data.get("regularized_improvement_ppm") is None else int(data["regularized_improvement_ppm"]),
        status=str(data["status"]),
        proposer_ref=str(data["proposer_ref"]),
        validator_ref=str(data["validator_ref"]),
        validated_at=int(data["validated_at"]),
        validation_hash=str(data["validation_hash"]),
    )
    result.validate()
    return result


def selection_to_dict(value: StructuralSelectionReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["candidate_hashes"] = list(value.candidate_hashes)
    data["validation_hashes"] = list(value.validation_hashes)
    return data


def selection_from_dict(data: Mapping[str, object]) -> StructuralSelectionReceipt:
    result = StructuralSelectionReceipt(
        selection_ref=str(data["selection_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        pair_key=str(data["pair_key"]),
        base_graph_hash=str(data["base_graph_hash"]),
        policy_hash=str(data["policy_hash"]),
        history_hash=str(data["history_hash"]),
        candidate_hashes=tuple(str(value) for value in data.get("candidate_hashes", [])),
        validation_hashes=tuple(str(value) for value in data.get("validation_hashes", [])),
        selected_candidate_hash=None if data.get("selected_candidate_hash") is None else str(data["selected_candidate_hash"]),
        selected_validation_hash=None if data.get("selected_validation_hash") is None else str(data["selected_validation_hash"]),
        selected_regularized_improvement_ppm=None if data.get("selected_regularized_improvement_ppm") is None else int(data["selected_regularized_improvement_ppm"]),
        status=str(data["status"]),
        selector_ref=str(data["selector_ref"]),
        selected_at=int(data["selected_at"]),
        selection_hash=str(data["selection_hash"]),
    )
    result.validate()
    return result


def review_to_dict(value: StructuralSelectionReviewReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> StructuralSelectionReviewReceipt:
    result = StructuralSelectionReviewReceipt(
        selection_hash=str(data["selection_hash"]),
        selected_candidate_hash=None if data.get("selected_candidate_hash") is None else str(data["selected_candidate_hash"]),
        decision=str(data["decision"]),
        rationale_ref=str(data["rationale_ref"]),
        selector_ref=str(data["selector_ref"]),
        proposer_ref=None if data.get("proposer_ref") is None else str(data["proposer_ref"]),
        reviewer_ref=str(data["reviewer_ref"]),
        reviewed_at=int(data["reviewed_at"]),
        review_hash=str(data["review_hash"]),
    )
    result.validate()
    return result


def revision_to_dict(value: ValidatedDependencyGraphRevisionReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = graph_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structural_validation_policy (
            subject_identity_ref TEXT PRIMARY KEY,
            policy_ref TEXT NOT NULL UNIQUE,
            policy_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structural_validation_candidate (
            candidate_hash TEXT PRIMARY KEY,
            candidate_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            base_graph_hash TEXT NOT NULL,
            policy_hash TEXT NOT NULL,
            history_hash TEXT NOT NULL,
            candidate_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structural_validation_receipt (
            validation_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL UNIQUE,
            receipt_json TEXT NOT NULL,
            cases_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structural_selection_receipt (
            selection_hash TEXT PRIMARY KEY,
            selection_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            base_graph_hash TEXT NOT NULL,
            policy_hash TEXT NOT NULL,
            history_hash TEXT NOT NULL,
            selection_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structural_selection_review (
            review_hash TEXT PRIMARY KEY,
            selection_hash TEXT NOT NULL UNIQUE,
            review_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS structural_validation_history (
            revision_hash TEXT PRIMARY KEY,
            selection_hash TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            base_graph_hash TEXT NOT NULL,
            new_graph_hash TEXT NOT NULL,
            base_graph_json TEXT NOT NULL,
            new_graph_json TEXT NOT NULL,
            candidate_json TEXT NOT NULL,
            validation_json TEXT NOT NULL,
            selection_json TEXT NOT NULL,
            review_json TEXT NOT NULL,
            revision_json TEXT NOT NULL
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
        raise PermissionError("structural validation authority failed: " + ",".join(dict.fromkeys(failures)))


def _policy(conn: sqlite3.Connection, subject: str) -> StructuralValidationPolicy:
    row = conn.execute("SELECT policy_json FROM structural_validation_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is None:
        raise ValueError("structural validation policy is not registered")
    return policy_from_dict(json.loads(row[0]))


def _candidate(conn: sqlite3.Connection, candidate_hash: str) -> StructuralValidationCandidate:
    row = conn.execute("SELECT candidate_json FROM structural_validation_candidate WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("unknown structural validation candidate")
    return candidate_from_dict(json.loads(row[0]))


def _validation(conn: sqlite3.Connection, candidate_hash: str) -> HeldOutStructuralValidationReceipt:
    row = conn.execute("SELECT receipt_json FROM structural_validation_receipt WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("candidate has no held-out validation")
    return validation_from_dict(json.loads(row[0]))


def _selection(conn: sqlite3.Connection, selection_hash: str) -> StructuralSelectionReceipt:
    row = conn.execute("SELECT selection_json FROM structural_selection_receipt WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None:
        raise ValueError("unknown structural selection")
    return selection_from_dict(json.loads(row[0]))


def _review(conn: sqlite3.Connection, selection_hash: str) -> StructuralSelectionReviewReceipt:
    row = conn.execute("SELECT review_json FROM structural_selection_review WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None:
        raise ValueError("structural selection review is not recorded")
    return review_from_dict(json.loads(row[0]))


def _current_validated_set(
    conn: sqlite3.Connection,
    *,
    subject: str,
    pair_key: str,
    base_graph_hash: str,
    policy_hash: str,
    history_hash: str,
) -> tuple[tuple[StructuralValidationCandidate, ...], tuple[HeldOutStructuralValidationReceipt, ...]]:
    rows = conn.execute(
        """
        SELECT c.candidate_json, v.receipt_json
        FROM structural_validation_candidate c
        JOIN structural_validation_receipt v ON v.candidate_hash=c.candidate_hash
        WHERE c.subject_identity_ref=? AND c.pair_key=? AND c.base_graph_hash=? AND c.policy_hash=? AND c.history_hash=?
        ORDER BY c.candidate_hash
        """,
        (subject, pair_key, base_graph_hash, policy_hash, history_hash),
    ).fetchall()
    candidates = tuple(candidate_from_dict(json.loads(row[0])) for row in rows)
    validations = tuple(validation_from_dict(json.loads(row[1])) for row in rows)
    return candidates, validations


def action_register_policy(value: StructuralValidationPolicy) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_structural_validation_policy",
        "subject_identity_ref": value.subject_identity_ref,
        "policy_hash": value.policy_hash,
        "evaluation_modulus": value.evaluation_modulus,
        "edge_penalty_ppm": value.edge_penalty_ppm,
    }


def action_register_candidate(value: StructuralValidationCandidate) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_structural_candidate",
        "candidate_hash": value.candidate_hash,
        "base_graph_hash": value.proposal.base_graph_hash,
        "policy_hash": value.policy_hash,
        "history_hash": value.history_hash,
        "direction": value.proposal.direction,
    }


def action_record_validation(value: HeldOutStructuralValidationReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_heldout_validation",
        "candidate_hash": value.candidate_hash,
        "validation_hash": value.validation_hash,
        "status": value.status,
        "regularized_improvement_ppm": value.regularized_improvement_ppm,
    }


def action_finalize_selection(value: StructuralSelectionReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "finalize_structural_selection",
        "selection_hash": value.selection_hash,
        "candidate_hashes": list(value.candidate_hashes),
        "validation_hashes": list(value.validation_hashes),
        "selected_candidate_hash": value.selected_candidate_hash,
        "status": value.status,
    }


def action_record_selection_review(value: StructuralSelectionReviewReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_structural_selection_review",
        "selection_hash": value.selection_hash,
        "review_hash": value.review_hash,
        "decision": value.decision,
    }


def action_apply_validated_selection(value: ValidatedDependencyGraphRevisionReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "apply_validated_structural_selection",
        "selection_hash": value.selection_hash,
        "validation_hash": value.validation_hash,
        "review_hash": value.review_hash,
        "candidate_hash": value.candidate_hash,
        "base_graph_hash": value.base_graph_hash,
        "new_graph_hash": value.new_graph_hash,
        "revision_hash": value.revision_hash,
    }


def _register_policy(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> StructuralValidationPolicy:
    subject = str(payload["subject_identity_ref"])
    policy = make_structural_validation_policy(
        policy_ref=str(payload["policy_ref"]),
        subject_identity_ref=subject,
        evaluation_modulus=int(payload.get("evaluation_modulus", 5)),
        min_selection_samples=int(payload.get("min_selection_samples", 6)),
        min_evaluation_samples=int(payload.get("min_evaluation_samples", 2)),
        dependency_threshold_bps=int(payload.get("dependency_threshold_bps", 1000)),
        edge_penalty_ppm=int(payload.get("edge_penalty_ppm", 10_000)),
        registered_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_register_policy(policy),
        required_role=ROLE_VALIDATION_POLICY_KEEPER,
        required_scope=verification_scope(subject),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT policy_json FROM structural_validation_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = policy_from_dict(json.loads(row[0]))
        if current == policy:
            return current
        raise ValueError("structural validation policy is immutable once registered")
    conn.execute(
        "INSERT INTO structural_validation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)",
        (subject, policy.policy_ref, json.dumps(policy_to_dict(policy), sort_keys=True, separators=(",", ":"))),
    )
    return policy


def _register_candidate(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> StructuralValidationCandidate:
    subject = str(payload["subject_identity_ref"])
    pair_key = str(payload["pair_key"])
    policy = _policy(conn, subject)
    base_graph = _graph(conn, subject)
    samples = _pair_samples(conn, pair_key)
    candidate = make_structural_validation_candidate(
        candidate_ref=str(payload["candidate_ref"]),
        base_graph=base_graph,
        samples=samples,
        policy=policy,
        direction=str(payload["direction"]),
        reason_ref=str(payload["reason_ref"]),
        proposer_ref=grant.subject_ref,
        created_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_register_candidate(candidate),
        required_role=ROLE_STRUCTURAL_CANDIDATE_PROPOSER,
        required_scope=verification_scope(subject),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT candidate_json FROM structural_validation_candidate WHERE candidate_ref=?", (candidate.candidate_ref,)).fetchone()
    if row is not None:
        current = candidate_from_dict(json.loads(row[0]))
        if current == candidate:
            return current
        raise ValueError("structural candidate_ref is immutable once registered")
    conn.execute(
        "INSERT INTO structural_validation_candidate(candidate_hash,candidate_ref,subject_identity_ref,pair_key,base_graph_hash,policy_hash,history_hash,candidate_json) VALUES(?,?,?,?,?,?,?,?)",
        (
            candidate.candidate_hash,
            candidate.candidate_ref,
            subject,
            pair_key,
            candidate.proposal.base_graph_hash,
            candidate.policy_hash,
            candidate.history_hash,
            json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":")),
        ),
    )
    return candidate


def _record_validation(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    candidate = _candidate(conn, str(payload["candidate_hash"]))
    policy = _policy(conn, candidate.subject_identity_ref)
    base_graph = _graph(conn, candidate.subject_identity_ref)
    samples = _pair_samples(conn, candidate.pair_key)
    if dependency_history_hash(samples) != candidate.history_hash:
        raise ValueError("structural candidate is stale; dependency history changed before held-out validation")
    cases, validation = validate_structural_candidate(
        candidate=candidate,
        base_graph=base_graph,
        samples=samples,
        policy=policy,
        validator_ref=grant.subject_ref,
        validated_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_record_validation(validation),
        required_role=ROLE_HELDOUT_VALIDATOR,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT receipt_json FROM structural_validation_receipt WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone()
    if row is not None:
        current = validation_from_dict(json.loads(row[0]))
        if current == validation:
            return cases, current
        raise ValueError("held-out validation is immutable once recorded")
    conn.execute(
        "INSERT INTO structural_validation_receipt(validation_hash,candidate_hash,receipt_json,cases_json) VALUES(?,?,?,?)",
        (
            validation.validation_hash,
            candidate.candidate_hash,
            json.dumps(validation_to_dict(validation), sort_keys=True, separators=(",", ":")),
            json.dumps([heldout_case_to_dict(item) for item in cases], sort_keys=True, separators=(",", ":")),
        ),
    )
    return cases, validation


def _finalize_selection(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> StructuralSelectionReceipt:
    subject = str(payload["subject_identity_ref"])
    pair_key = str(payload["pair_key"])
    policy = _policy(conn, subject)
    current_graph = _graph(conn, subject)
    history_hash = dependency_history_hash(_pair_samples(conn, pair_key))
    candidates, validations = _current_validated_set(
        conn,
        subject=subject,
        pair_key=pair_key,
        base_graph_hash=current_graph.graph_hash,
        policy_hash=policy.policy_hash,
        history_hash=history_hash,
    )
    if not candidates:
        raise ValueError("structural selection requires at least one current held-out validation")
    selection = select_structural_candidate(
        selection_ref=str(payload["selection_ref"]),
        candidates=candidates,
        validations=validations,
        selector_ref=grant.subject_ref,
        selected_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_finalize_selection(selection),
        required_role=ROLE_STRUCTURAL_SELECTOR,
        required_scope=verification_scope(subject),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT selection_json FROM structural_selection_receipt WHERE selection_ref=?", (selection.selection_ref,)).fetchone()
    if row is not None:
        current = selection_from_dict(json.loads(row[0]))
        if current == selection:
            return current
        raise ValueError("structural selection_ref is immutable once finalized")
    conn.execute(
        "INSERT INTO structural_selection_receipt(selection_hash,selection_ref,subject_identity_ref,pair_key,base_graph_hash,policy_hash,history_hash,selection_json) VALUES(?,?,?,?,?,?,?,?)",
        (
            selection.selection_hash,
            selection.selection_ref,
            subject,
            pair_key,
            selection.base_graph_hash,
            selection.policy_hash,
            selection.history_hash,
            json.dumps(selection_to_dict(selection), sort_keys=True, separators=(",", ":")),
        ),
    )
    return selection


def _record_review(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> StructuralSelectionReviewReceipt:
    selection = _selection(conn, str(payload["selection_hash"]))
    selected_candidate = None if selection.selected_candidate_hash is None else _candidate(conn, selection.selected_candidate_hash)
    review = review_structural_selection(
        selection=selection,
        selected_candidate=selected_candidate,
        decision=str(payload["decision"]),
        rationale_ref=str(payload["rationale_ref"]),
        reviewer_ref=grant.subject_ref,
        reviewed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_record_selection_review(review),
        required_role=ROLE_STRUCTURAL_SELECTION_REVIEWER,
        required_scope=verification_scope(selection.subject_identity_ref),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT review_json FROM structural_selection_review WHERE selection_hash=?", (selection.selection_hash,)).fetchone()
    if row is not None:
        current = review_from_dict(json.loads(row[0]))
        if current == review:
            return current
        raise ValueError("structural selection review is immutable once recorded")
    conn.execute(
        "INSERT INTO structural_selection_review(review_hash,selection_hash,review_json) VALUES(?,?,?)",
        (review.review_hash, selection.selection_hash, json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":"))),
    )
    return review


def _apply(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    selection = _selection(conn, str(payload["selection_hash"]))
    review = _review(conn, selection.selection_hash)
    if selection.status != "SELECTED" or selection.selected_candidate_hash is None:
        raise ValueError("validated structural apply requires a selected candidate")
    candidate = _candidate(conn, selection.selected_candidate_hash)
    validation = _validation(conn, candidate.candidate_hash)
    policy = _policy(conn, selection.subject_identity_ref)
    current_graph = _graph(conn, selection.subject_identity_ref)
    samples = _pair_samples(conn, selection.pair_key)
    current_history_hash = dependency_history_hash(samples)
    if current_history_hash != selection.history_hash or current_history_hash != candidate.history_hash:
        raise ValueError("stale structural selection; dependency history changed after selection")
    if policy.policy_hash != selection.policy_hash or current_graph.graph_hash != selection.base_graph_hash:
        raise ValueError("stale structural selection policy or base graph")
    current_candidates, current_validations = _current_validated_set(
        conn,
        subject=selection.subject_identity_ref,
        pair_key=selection.pair_key,
        base_graph_hash=current_graph.graph_hash,
        policy_hash=policy.policy_hash,
        history_hash=current_history_hash,
    )
    fresh_selection = select_structural_candidate(
        selection_ref=selection.selection_ref,
        candidates=current_candidates,
        validations=current_validations,
        selector_ref=selection.selector_ref,
        selected_at=selection.selected_at,
    )
    if fresh_selection != selection:
        raise ValueError("stale structural selection; validated candidate set changed after selection")
    new_graph, revision = apply_validated_structural_selection(
        current_graph=current_graph,
        candidate=candidate,
        validation=validation,
        selection=selection,
        review=review,
        applier_ref=grant.subject_ref,
        applied_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_apply_validated_selection(revision),
        required_role=ROLE_VALIDATED_STRUCTURAL_APPLIER,
        required_scope=verification_scope(selection.subject_identity_ref),
        enforcement=enforcement,
    )
    if conn.execute("SELECT 1 FROM structural_validation_history WHERE selection_hash=?", (selection.selection_hash,)).fetchone() is not None:
        raise ValueError("structural selection has already been applied")
    base_json = json.dumps(graph_to_dict(current_graph), sort_keys=True, separators=(",", ":"))
    new_json = json.dumps(graph_to_dict(new_graph), sort_keys=True, separators=(",", ":"))
    conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?", (new_json, selection.subject_identity_ref))
    conn.execute(
        "INSERT INTO structural_validation_history(revision_hash,selection_hash,subject_identity_ref,base_graph_hash,new_graph_hash,base_graph_json,new_graph_json,candidate_json,validation_json,selection_json,review_json,revision_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            revision.revision_hash,
            selection.selection_hash,
            selection.subject_identity_ref,
            current_graph.graph_hash,
            new_graph.graph_hash,
            base_json,
            new_json,
            json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":")),
            json.dumps(validation_to_dict(validation), sort_keys=True, separators=(",", ":")),
            json.dumps(selection_to_dict(selection), sort_keys=True, separators=(",", ":")),
            json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":")),
            json.dumps(revision_to_dict(revision), sort_keys=True, separators=(",", ":")),
        ),
    )
    return new_graph, revision


def _state(conn: sqlite3.Connection) -> dict[str, object]:
    policies = conn.execute("SELECT policy_json FROM structural_validation_policy ORDER BY subject_identity_ref").fetchall()
    candidates = conn.execute("SELECT candidate_hash FROM structural_validation_candidate ORDER BY candidate_hash").fetchall()
    validations = conn.execute("SELECT validation_hash FROM structural_validation_receipt ORDER BY validation_hash").fetchall()
    selections = conn.execute("SELECT selection_hash FROM structural_selection_receipt ORDER BY selection_hash").fetchall()
    reviews = conn.execute("SELECT review_hash FROM structural_selection_review ORDER BY review_hash").fetchall()
    revisions = conn.execute("SELECT revision_hash FROM structural_validation_history ORDER BY revision_hash").fetchall()
    return {
        "policies": [policy_to_dict(policy_from_dict(json.loads(row[0]))) for row in policies],
        "candidate_hashes": [str(row[0]) for row in candidates],
        "validation_hashes": [str(row[0]) for row in validations],
        "selection_hashes": [str(row[0]) for row in selections],
        "review_hashes": [str(row[0]) for row in reviews],
        "revision_hashes": [str(row[0]) for row in revisions],
    }


def execute_structural_validation_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != STRUCTURE_PROTOCOL:
        raise ValueError("unsupported structural validation protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in STRUCTURE_OPERATIONS:
        raise ValueError("unsupported structural validation operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_structural_validation_state":
            return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, **_state(conn)}
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_structural_validation_policy":
            policy = _register_policy(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, "policy": policy_to_dict(policy)}
        if operation == "register_structural_candidate":
            candidate = _register_candidate(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, "candidate": candidate_to_dict(candidate)}
        if operation == "record_heldout_validation":
            cases, validation = _record_validation(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, "validation": validation_to_dict(validation), "cases": [heldout_case_to_dict(item) for item in cases]}
        if operation == "finalize_structural_selection":
            selection = _finalize_selection(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, "selection": selection_to_dict(selection)}
        if operation == "record_structural_selection_review":
            review = _record_review(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, "review": review_to_dict(review)}
        new_graph, revision = _apply(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
        conn.execute("COMMIT")
        return {"protocol": STRUCTURE_PROTOCOL, "request_id": request_id, "ok": True, "graph": graph_to_dict(new_graph), "revision": revision_to_dict(revision)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
