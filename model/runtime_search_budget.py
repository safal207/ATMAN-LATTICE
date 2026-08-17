from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.runtime_dependency_graph import _graph, _pair_samples, graph_to_dict
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_structural_validation import (
    _candidate,
    _connect as structure_connect,
    _policy as structural_policy,
    candidate_from_dict,
    candidate_to_dict,
    heldout_case_to_dict,
    validation_from_dict,
    validation_to_dict,
)
from model.runtime_verification import verification_scope
from model.search_budget import (
    HeldOutSearchBudgetPolicy,
    HeldOutSearchReservation,
    SearchAdjustedValidationReceipt,
    SearchBudgetSelectionReceipt,
    SearchBudgetSelectionReviewReceipt,
    SearchBudgetedGraphRevisionReceipt,
    apply_search_budgeted_selection,
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    search_context_hash,
    search_family_hash,
    select_search_budget_candidate,
)
from model.structural_validation import dependency_history_hash

SEARCH_PROTOCOL = "ATMAN-SEARCH/1.16"
SEARCH_OPERATIONS = {
    "register_search_budget_policy",
    "reserve_heldout_evaluation",
    "evaluate_reserved_candidate",
    "finalize_search_budget_selection",
    "record_search_budget_selection_review",
    "apply_search_budgeted_selection",
    "get_search_budget_state",
}

ROLE_SEARCH_POLICY_KEEPER = "HELDOUT_SEARCH_POLICY_KEEPER"
ROLE_SEARCH_BUDGET_KEEPER = "HELDOUT_SEARCH_BUDGET_KEEPER"
ROLE_SEARCH_EVALUATOR = "HELDOUT_SEARCH_EVALUATOR"
ROLE_SEARCH_SELECTOR = "SEARCH_BUDGET_MODEL_SELECTOR"
ROLE_SEARCH_REVIEWER = "SEARCH_BUDGET_SELECTION_REVIEWER"
ROLE_SEARCH_APPLIER = "SEARCH_BUDGETED_STRUCTURAL_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def policy_to_dict(value: HeldOutSearchBudgetPolicy) -> dict[str, object]:
    value.validate()
    return asdict(value)


def policy_from_dict(data: Mapping[str, object]) -> HeldOutSearchBudgetPolicy:
    result = HeldOutSearchBudgetPolicy(
        policy_ref=str(data["policy_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        max_unique_evaluations=int(data["max_unique_evaluations"]),
        base_min_regularized_improvement_ppm=int(data["base_min_regularized_improvement_ppm"]),
        multiplicity_penalty_ppm=int(data["multiplicity_penalty_ppm"]),
        registered_at=int(data["registered_at"]),
        policy_hash=str(data["policy_hash"]),
    )
    result.validate()
    return result


def reservation_to_dict(value: HeldOutSearchReservation) -> dict[str, object]:
    value.validate()
    return asdict(value)


def reservation_from_dict(data: Mapping[str, object]) -> HeldOutSearchReservation:
    result = HeldOutSearchReservation(
        candidate_hash=str(data["candidate_hash"]),
        family_hash=str(data["family_hash"]),
        context_hash=str(data["context_hash"]),
        search_policy_hash=str(data["search_policy_hash"]),
        ordinal=int(data["ordinal"]),
        max_unique_evaluations=int(data["max_unique_evaluations"]),
        effective_min_regularized_improvement_ppm=int(data["effective_min_regularized_improvement_ppm"]),
        budget_keeper_ref=str(data["budget_keeper_ref"]),
        reserved_at=int(data["reserved_at"]),
        reservation_hash=str(data["reservation_hash"]),
    )
    result.validate()
    return result


def evaluation_to_dict(value: SearchAdjustedValidationReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def evaluation_from_dict(data: Mapping[str, object]) -> SearchAdjustedValidationReceipt:
    result = SearchAdjustedValidationReceipt(
        candidate_hash=str(data["candidate_hash"]),
        reservation_hash=str(data["reservation_hash"]),
        underlying_validation_hash=str(data["underlying_validation_hash"]),
        family_hash=str(data["family_hash"]),
        context_hash=str(data["context_hash"]),
        ordinal=int(data["ordinal"]),
        effective_min_regularized_improvement_ppm=int(data["effective_min_regularized_improvement_ppm"]),
        underlying_status=str(data["underlying_status"]),
        regularized_improvement_ppm=None if data.get("regularized_improvement_ppm") is None else int(data["regularized_improvement_ppm"]),
        search_adjusted_margin_ppm=None if data.get("search_adjusted_margin_ppm") is None else int(data["search_adjusted_margin_ppm"]),
        status=str(data["status"]),
        proposer_ref=str(data["proposer_ref"]),
        budget_keeper_ref=str(data["budget_keeper_ref"]),
        evaluator_ref=str(data["evaluator_ref"]),
        evaluated_at=int(data["evaluated_at"]),
        evaluation_hash=str(data["evaluation_hash"]),
    )
    result.validate()
    return result


def selection_to_dict(value: SearchBudgetSelectionReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["family_reservation_hashes"] = list(value.family_reservation_hashes)
    data["current_candidate_hashes"] = list(value.current_candidate_hashes)
    data["current_evaluation_hashes"] = list(value.current_evaluation_hashes)
    return data


def selection_from_dict(data: Mapping[str, object]) -> SearchBudgetSelectionReceipt:
    result = SearchBudgetSelectionReceipt(
        selection_ref=str(data["selection_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        pair_key=str(data["pair_key"]),
        base_graph_hash=str(data["base_graph_hash"]),
        structural_policy_hash=str(data["structural_policy_hash"]),
        search_policy_hash=str(data["search_policy_hash"]),
        history_hash=str(data["history_hash"]),
        context_hash=str(data["context_hash"]),
        family_hash=str(data["family_hash"]),
        family_reservation_hashes=tuple(str(v) for v in data.get("family_reservation_hashes", [])),
        current_candidate_hashes=tuple(str(v) for v in data.get("current_candidate_hashes", [])),
        current_evaluation_hashes=tuple(str(v) for v in data.get("current_evaluation_hashes", [])),
        budget_used=int(data["budget_used"]),
        budget_remaining=int(data["budget_remaining"]),
        selected_candidate_hash=None if data.get("selected_candidate_hash") is None else str(data["selected_candidate_hash"]),
        selected_evaluation_hash=None if data.get("selected_evaluation_hash") is None else str(data["selected_evaluation_hash"]),
        selected_search_adjusted_margin_ppm=None if data.get("selected_search_adjusted_margin_ppm") is None else int(data["selected_search_adjusted_margin_ppm"]),
        status=str(data["status"]),
        selector_ref=str(data["selector_ref"]),
        selected_at=int(data["selected_at"]),
        selection_hash=str(data["selection_hash"]),
    )
    result.validate()
    return result


def review_to_dict(value: SearchBudgetSelectionReviewReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> SearchBudgetSelectionReviewReceipt:
    result = SearchBudgetSelectionReviewReceipt(
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


def revision_to_dict(value: SearchBudgetedGraphRevisionReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = structure_connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heldout_search_budget_policy (
            subject_identity_ref TEXT PRIMARY KEY,
            policy_ref TEXT NOT NULL UNIQUE,
            policy_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heldout_search_reservation (
            reservation_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL UNIQUE,
            family_hash TEXT NOT NULL,
            context_hash TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            reservation_json TEXT NOT NULL,
            UNIQUE(family_hash, ordinal)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heldout_search_evaluation (
            evaluation_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL UNIQUE,
            reservation_hash TEXT NOT NULL UNIQUE,
            underlying_validation_json TEXT NOT NULL,
            evaluation_json TEXT NOT NULL,
            cases_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heldout_search_selection (
            selection_hash TEXT PRIMARY KEY,
            selection_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            family_hash TEXT NOT NULL,
            selection_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heldout_search_review (
            review_hash TEXT PRIMARY KEY,
            selection_hash TEXT NOT NULL UNIQUE,
            review_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heldout_search_revision_history (
            revision_hash TEXT PRIMARY KEY,
            selection_hash TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            base_graph_hash TEXT NOT NULL,
            new_graph_hash TEXT NOT NULL,
            base_graph_json TEXT NOT NULL,
            new_graph_json TEXT NOT NULL,
            reservation_json TEXT NOT NULL,
            candidate_json TEXT NOT NULL,
            underlying_validation_json TEXT NOT NULL,
            evaluation_json TEXT NOT NULL,
            selection_json TEXT NOT NULL,
            review_json TEXT NOT NULL,
            revision_json TEXT NOT NULL
        )
    """)
    return conn


def _enforce(grant: AuthorityGrant, proof: AuthorityProof, *, action: object, required_role: str, required_scope: str, enforcement: EnforcementContext) -> None:
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
        raise PermissionError("search budget authority failed: " + ",".join(dict.fromkeys(failures)))


def _policy(conn: sqlite3.Connection, subject: str) -> HeldOutSearchBudgetPolicy:
    row = conn.execute("SELECT policy_json FROM heldout_search_budget_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is None:
        raise ValueError("held-out search budget policy is not registered")
    return policy_from_dict(json.loads(row[0]))


def _reservation(conn: sqlite3.Connection, candidate_hash: str) -> HeldOutSearchReservation:
    row = conn.execute("SELECT reservation_json FROM heldout_search_reservation WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("candidate has no held-out search reservation")
    return reservation_from_dict(json.loads(row[0]))


def _evaluation_bundle(conn: sqlite3.Connection, candidate_hash: str):
    row = conn.execute("SELECT underlying_validation_json,evaluation_json FROM heldout_search_evaluation WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("candidate has no search-adjusted evaluation")
    return validation_from_dict(json.loads(row[0])), evaluation_from_dict(json.loads(row[1]))


def _selection(conn: sqlite3.Connection, selection_hash: str) -> SearchBudgetSelectionReceipt:
    row = conn.execute("SELECT selection_json FROM heldout_search_selection WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None:
        raise ValueError("unknown search budget selection")
    return selection_from_dict(json.loads(row[0]))


def _review(conn: sqlite3.Connection, selection_hash: str) -> SearchBudgetSelectionReviewReceipt:
    row = conn.execute("SELECT review_json FROM heldout_search_review WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None:
        raise ValueError("search budget selection review is not recorded")
    return review_from_dict(json.loads(row[0]))


def _family_reservations(conn: sqlite3.Connection, family_hash: str) -> tuple[HeldOutSearchReservation, ...]:
    rows = conn.execute("SELECT reservation_json FROM heldout_search_reservation WHERE family_hash=? ORDER BY ordinal", (family_hash,)).fetchall()
    return tuple(reservation_from_dict(json.loads(row[0])) for row in rows)


def _family_rows(conn: sqlite3.Connection, *, subject: str, pair_key: str, structural_policy_hash: str):
    rows = conn.execute("""
        SELECT r.reservation_json, c.candidate_json
        FROM heldout_search_reservation r
        JOIN structural_validation_candidate c ON c.candidate_hash=r.candidate_hash
        WHERE c.subject_identity_ref=? AND c.pair_key=? AND c.policy_hash=?
        ORDER BY r.ordinal
    """, (subject, pair_key, structural_policy_hash)).fetchall()
    return tuple((reservation_from_dict(json.loads(row[0])), candidate_from_dict(json.loads(row[1]))) for row in rows)


def action_register_policy(value: HeldOutSearchBudgetPolicy) -> dict[str, object]:
    value.validate()
    return {"operation": "register_search_budget_policy", "subject_identity_ref": value.subject_identity_ref, "policy_hash": value.policy_hash, "max_unique_evaluations": value.max_unique_evaluations, "multiplicity_penalty_ppm": value.multiplicity_penalty_ppm}


def action_reserve(value: HeldOutSearchReservation) -> dict[str, object]:
    value.validate()
    return {"operation": "reserve_heldout_evaluation", "candidate_hash": value.candidate_hash, "reservation_hash": value.reservation_hash, "family_hash": value.family_hash, "ordinal": value.ordinal, "effective_min_regularized_improvement_ppm": value.effective_min_regularized_improvement_ppm}


def action_evaluate(value: SearchAdjustedValidationReceipt) -> dict[str, object]:
    value.validate()
    return {"operation": "evaluate_reserved_candidate", "candidate_hash": value.candidate_hash, "reservation_hash": value.reservation_hash, "evaluation_hash": value.evaluation_hash, "status": value.status, "search_adjusted_margin_ppm": value.search_adjusted_margin_ppm}


def action_finalize_selection(value: SearchBudgetSelectionReceipt) -> dict[str, object]:
    value.validate()
    return {"operation": "finalize_search_budget_selection", "selection_hash": value.selection_hash, "family_reservation_hashes": list(value.family_reservation_hashes), "current_candidate_hashes": list(value.current_candidate_hashes), "selected_candidate_hash": value.selected_candidate_hash, "status": value.status}


def action_review(value: SearchBudgetSelectionReviewReceipt) -> dict[str, object]:
    value.validate()
    return {"operation": "record_search_budget_selection_review", "selection_hash": value.selection_hash, "review_hash": value.review_hash, "decision": value.decision}


def action_apply(value: SearchBudgetedGraphRevisionReceipt) -> dict[str, object]:
    value.validate()
    return {"operation": "apply_search_budgeted_selection", "selection_hash": value.selection_hash, "review_hash": value.review_hash, "candidate_hash": value.candidate_hash, "evaluation_hash": value.evaluation_hash, "base_graph_hash": value.base_graph_hash, "new_graph_hash": value.new_graph_hash, "revision_hash": value.revision_hash}


def _register_policy(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    subject = str(payload["subject_identity_ref"])
    policy = make_search_budget_policy(
        policy_ref=str(payload["policy_ref"]),
        subject_identity_ref=subject,
        max_unique_evaluations=int(payload.get("max_unique_evaluations", 8)),
        base_min_regularized_improvement_ppm=int(payload.get("base_min_regularized_improvement_ppm", 0)),
        multiplicity_penalty_ppm=int(payload.get("multiplicity_penalty_ppm", 10_000)),
        registered_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_register_policy(policy), required_role=ROLE_SEARCH_POLICY_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT policy_json FROM heldout_search_budget_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = policy_from_dict(json.loads(row[0]))
        if current == policy:
            return current
        raise ValueError("held-out search budget policy is immutable once registered")
    conn.execute("INSERT INTO heldout_search_budget_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (subject, policy.policy_ref, json.dumps(policy_to_dict(policy), sort_keys=True, separators=(",", ":"))))
    return policy


def _assert_candidate_fresh(conn: sqlite3.Connection, candidate, structural, current_graph) -> tuple[object, ...]:
    samples = _pair_samples(conn, candidate.pair_key)
    if candidate.policy_hash != structural.policy_hash or candidate.proposal.base_graph_hash != current_graph.graph_hash or candidate.history_hash != dependency_history_hash(samples):
        raise ValueError("structural candidate is stale for search-budget use")
    return samples


def _reserve(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    candidate = _candidate(conn, str(payload["candidate_hash"]))
    policy = _policy(conn, candidate.subject_identity_ref)
    structural = structural_policy(conn, candidate.subject_identity_ref)
    current_graph = _graph(conn, candidate.subject_identity_ref)
    _assert_candidate_fresh(conn, candidate, structural, current_graph)
    if conn.execute("SELECT 1 FROM structural_validation_receipt WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone() is not None:
        raise ValueError("held-out already exposed outside search-budget plane")
    family_hash = search_family_hash(candidate, policy)
    prior = _family_reservations(conn, family_hash)
    reservation = reserve_heldout_search(candidate=candidate, policy=policy, prior_reservations=prior, budget_keeper_ref=grant.subject_ref, reserved_at=enforcement.now)
    if reservation.budget_keeper_ref != grant.subject_ref:
        raise PermissionError("existing held-out reservation belongs to a different budget keeper")
    _enforce(grant, proof, action=action_reserve(reservation), required_role=ROLE_SEARCH_BUDGET_KEEPER, required_scope=verification_scope(candidate.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT reservation_json FROM heldout_search_reservation WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone()
    if row is not None:
        current = reservation_from_dict(json.loads(row[0]))
        if current == reservation:
            return current
        raise ValueError("held-out reservation is immutable once recorded")
    conn.execute("INSERT INTO heldout_search_reservation(reservation_hash,candidate_hash,family_hash,context_hash,ordinal,reservation_json) VALUES(?,?,?,?,?,?)", (reservation.reservation_hash, candidate.candidate_hash, reservation.family_hash, reservation.context_hash, reservation.ordinal, json.dumps(reservation_to_dict(reservation), sort_keys=True, separators=(",", ":"))))
    return reservation


def _evaluate(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    candidate = _candidate(conn, str(payload["candidate_hash"]))
    reservation = _reservation(conn, candidate.candidate_hash)
    policy = _policy(conn, candidate.subject_identity_ref)
    structural = structural_policy(conn, candidate.subject_identity_ref)
    current_graph = _graph(conn, candidate.subject_identity_ref)
    samples = _assert_candidate_fresh(conn, candidate, structural, current_graph)
    if conn.execute("SELECT 1 FROM structural_validation_receipt WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone() is not None:
        raise ValueError("parallel unbudgeted held-out exposure detected")
    cases, underlying, evaluation = evaluate_reserved_candidate(candidate=candidate, reservation=reservation, base_graph=current_graph, samples=samples, structural_policy=structural, search_policy=policy, evaluator_ref=grant.subject_ref, evaluated_at=enforcement.now)
    _enforce(grant, proof, action=action_evaluate(evaluation), required_role=ROLE_SEARCH_EVALUATOR, required_scope=verification_scope(candidate.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT evaluation_json FROM heldout_search_evaluation WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone()
    if row is not None:
        current = evaluation_from_dict(json.loads(row[0]))
        if current == evaluation:
            return cases, underlying, current
        raise ValueError("search-adjusted held-out evaluation is immutable once recorded")
    conn.execute("INSERT INTO heldout_search_evaluation(evaluation_hash,candidate_hash,reservation_hash,underlying_validation_json,evaluation_json,cases_json) VALUES(?,?,?,?,?,?)", (evaluation.evaluation_hash, candidate.candidate_hash, reservation.reservation_hash, json.dumps(validation_to_dict(underlying), sort_keys=True, separators=(",", ":")), json.dumps(evaluation_to_dict(evaluation), sort_keys=True, separators=(",", ":")), json.dumps([heldout_case_to_dict(item) for item in cases], sort_keys=True, separators=(",", ":"))))
    return cases, underlying, evaluation


def _current_search_state(conn: sqlite3.Connection, *, subject: str, pair_key: str):
    structural = structural_policy(conn, subject)
    policy = _policy(conn, subject)
    current_graph = _graph(conn, subject)
    samples = _pair_samples(conn, pair_key)
    history_hash = dependency_history_hash(samples)
    family_rows = _family_rows(conn, subject=subject, pair_key=pair_key, structural_policy_hash=structural.policy_hash)
    if not family_rows:
        raise ValueError("search budget selection requires at least one reservation")
    all_reservations = tuple(row[0] for row in family_rows)
    family_hashes = {item.family_hash for item in all_reservations}
    if len(family_hashes) != 1:
        raise ValueError("search budget family state is inconsistent")
    if next(iter(family_hashes)) != search_family_hash(family_rows[0][1], policy):
        raise ValueError("search budget family/policy mismatch")
    current = [(reservation, candidate) for reservation, candidate in family_rows if candidate.proposal.base_graph_hash == current_graph.graph_hash and candidate.history_hash == history_hash]
    if not current:
        raise ValueError("no reserved candidates match current structural context")
    current_candidates = tuple(candidate for _, candidate in current)
    current_evaluations = []
    for reservation, candidate in current:
        row = conn.execute("SELECT evaluation_json FROM heldout_search_evaluation WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone()
        if row is None:
            raise ValueError("search selection has pending reserved evaluation")
        current_evaluations.append(evaluation_from_dict(json.loads(row[0])))
    return structural, policy, current_graph, samples, all_reservations, current_candidates, tuple(current_evaluations)


def _finalize_selection(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    subject = str(payload["subject_identity_ref"])
    pair_key = str(payload["pair_key"])
    _, policy, _, _, reservations, candidates, evaluations = _current_search_state(conn, subject=subject, pair_key=pair_key)
    selection = select_search_budget_candidate(selection_ref=str(payload["selection_ref"]), current_candidates=candidates, current_evaluations=evaluations, all_family_reservations=reservations, search_policy=policy, selector_ref=grant.subject_ref, selected_at=enforcement.now)
    _enforce(grant, proof, action=action_finalize_selection(selection), required_role=ROLE_SEARCH_SELECTOR, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT selection_json FROM heldout_search_selection WHERE selection_ref=?", (selection.selection_ref,)).fetchone()
    if row is not None:
        current = selection_from_dict(json.loads(row[0]))
        if current == selection:
            return current
        raise ValueError("search selection_ref is immutable once finalized")
    conn.execute("INSERT INTO heldout_search_selection(selection_hash,selection_ref,subject_identity_ref,pair_key,family_hash,selection_json) VALUES(?,?,?,?,?,?)", (selection.selection_hash, selection.selection_ref, subject, pair_key, selection.family_hash, json.dumps(selection_to_dict(selection), sort_keys=True, separators=(",", ":"))))
    return selection


def _record_review(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    selection = _selection(conn, str(payload["selection_hash"]))
    selected_candidate = None if selection.selected_candidate_hash is None else _candidate(conn, selection.selected_candidate_hash)
    review = review_search_budget_selection(selection=selection, selected_candidate=selected_candidate, decision=str(payload["decision"]), rationale_ref=str(payload["rationale_ref"]), reviewer_ref=grant.subject_ref, reviewed_at=enforcement.now)
    _enforce(grant, proof, action=action_review(review), required_role=ROLE_SEARCH_REVIEWER, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT review_json FROM heldout_search_review WHERE selection_hash=?", (selection.selection_hash,)).fetchone()
    if row is not None:
        current = review_from_dict(json.loads(row[0]))
        if current == review:
            return current
        raise ValueError("search budget selection review is immutable once recorded")
    conn.execute("INSERT INTO heldout_search_review(review_hash,selection_hash,review_json) VALUES(?,?,?)", (review.review_hash, selection.selection_hash, json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":"))))
    return review


def _apply(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    selection = _selection(conn, str(payload["selection_hash"]))
    review = _review(conn, selection.selection_hash)
    if selection.status != "SELECTED" or selection.selected_candidate_hash is None:
        raise ValueError("search-budgeted apply requires a selected candidate")
    structural, policy, current_graph, _, reservations, candidates, evaluations = _current_search_state(conn, subject=selection.subject_identity_ref, pair_key=selection.pair_key)
    fresh = select_search_budget_candidate(selection_ref=selection.selection_ref, current_candidates=candidates, current_evaluations=evaluations, all_family_reservations=reservations, search_policy=policy, selector_ref=selection.selector_ref, selected_at=selection.selected_at)
    if fresh != selection:
        raise ValueError("stale search-budget selection; exposure or candidate state changed after selection")
    candidate = _candidate(conn, selection.selected_candidate_hash)
    reservation = _reservation(conn, candidate.candidate_hash)
    underlying, evaluation = _evaluation_bundle(conn, candidate.candidate_hash)
    if conn.execute("SELECT 1 FROM structural_validation_receipt WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone() is not None:
        raise ValueError("parallel unbudgeted held-out exposure detected before apply")
    new_graph, revision = apply_search_budgeted_selection(current_graph=current_graph, candidate=candidate, reservation=reservation, underlying_validation=underlying, evaluation=evaluation, selection=selection, review=review, applier_ref=grant.subject_ref, applied_at=enforcement.now)
    _enforce(grant, proof, action=action_apply(revision), required_role=ROLE_SEARCH_APPLIER, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    if conn.execute("SELECT 1 FROM heldout_search_revision_history WHERE selection_hash=?", (selection.selection_hash,)).fetchone() is not None:
        raise ValueError("search budget selection has already been applied")
    base_json = json.dumps(graph_to_dict(current_graph), sort_keys=True, separators=(",", ":"))
    new_json = json.dumps(graph_to_dict(new_graph), sort_keys=True, separators=(",", ":"))
    conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?", (new_json, selection.subject_identity_ref))
    conn.execute("INSERT INTO heldout_search_revision_history(revision_hash,selection_hash,subject_identity_ref,base_graph_hash,new_graph_hash,base_graph_json,new_graph_json,reservation_json,candidate_json,underlying_validation_json,evaluation_json,selection_json,review_json,revision_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (revision.revision_hash, selection.selection_hash, selection.subject_identity_ref, current_graph.graph_hash, new_graph.graph_hash, base_json, new_json, json.dumps(reservation_to_dict(reservation), sort_keys=True, separators=(",", ":")), json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":")), json.dumps(validation_to_dict(underlying), sort_keys=True, separators=(",", ":")), json.dumps(evaluation_to_dict(evaluation), sort_keys=True, separators=(",", ":")), json.dumps(selection_to_dict(selection), sort_keys=True, separators=(",", ":")), json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":")), json.dumps(revision_to_dict(revision), sort_keys=True, separators=(",", ":"))))
    return new_graph, revision


def _state(conn: sqlite3.Connection) -> dict[str, object]:
    policies = conn.execute("SELECT policy_json FROM heldout_search_budget_policy ORDER BY subject_identity_ref").fetchall()
    reservations = conn.execute("SELECT reservation_json FROM heldout_search_reservation ORDER BY family_hash,ordinal").fetchall()
    evaluations = conn.execute("SELECT evaluation_hash FROM heldout_search_evaluation ORDER BY evaluation_hash").fetchall()
    selections = conn.execute("SELECT selection_hash FROM heldout_search_selection ORDER BY selection_hash").fetchall()
    reviews = conn.execute("SELECT review_hash FROM heldout_search_review ORDER BY review_hash").fetchall()
    revisions = conn.execute("SELECT revision_hash FROM heldout_search_revision_history ORDER BY revision_hash").fetchall()
    return {
        "policies": [policy_to_dict(policy_from_dict(json.loads(row[0]))) for row in policies],
        "reservations": [reservation_to_dict(reservation_from_dict(json.loads(row[0]))) for row in reservations],
        "evaluation_hashes": [str(row[0]) for row in evaluations],
        "selection_hashes": [str(row[0]) for row in selections],
        "review_hashes": [str(row[0]) for row in reviews],
        "revision_hashes": [str(row[0]) for row in revisions],
    }


def execute_search_budget_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != SEARCH_PROTOCOL:
        raise ValueError("unsupported held-out search budget protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in SEARCH_OPERATIONS:
        raise ValueError("unsupported held-out search budget operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_search_budget_state":
            return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, **_state(conn)}
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_search_budget_policy":
            value = _register_policy(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, "policy": policy_to_dict(value)}
        if operation == "reserve_heldout_evaluation":
            value = _reserve(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, "reservation": reservation_to_dict(value)}
        if operation == "evaluate_reserved_candidate":
            cases, underlying, value = _evaluate(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, "underlying_validation": validation_to_dict(underlying), "evaluation": evaluation_to_dict(value), "cases": [heldout_case_to_dict(item) for item in cases]}
        if operation == "finalize_search_budget_selection":
            value = _finalize_selection(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, "selection": selection_to_dict(value)}
        if operation == "record_search_budget_selection_review":
            value = _record_review(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, "review": review_to_dict(value)}
        graph, revision = _apply(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
        conn.execute("COMMIT")
        return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "ok": True, "graph": graph_to_dict(graph), "revision": revision_to_dict(revision)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
