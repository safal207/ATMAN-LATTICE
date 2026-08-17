from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.model_revision import (
    CounterfactualReplayCase,
    CounterfactualReplayReceipt,
    ModelRevisionProposal,
    ModelRevisionReceipt,
    ModelRevisionReviewReceipt,
    apply_revision,
    make_model_revision_proposal,
    replay_revision,
    review_revision,
)
from model.runtime_calibration import (
    _connect as calibration_connect,
    _state as calibration_state,
    family_snapshot_to_dict,
    likelihood_from_dict,
)
from model.runtime_multihypothesis import (
    _distribution_for_candidate,
    _model,
    distribution_to_dict,
    model_from_dict,
    model_to_dict,
)
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import verification_scope

REVISION_PROTOCOL = "ATMAN-REVISION/1.13"
REVISION_OPERATIONS = {
    "register_revision_proposal",
    "record_counterfactual_replay",
    "record_revision_review",
    "apply_model_revision",
    "get_revision_state",
}

ROLE_REVISION_PROPOSER = "MODEL_REVISION_PROPOSER"
ROLE_REVISION_REPLAY_KEEPER = "MODEL_REVISION_REPLAY_KEEPER"
ROLE_REVISION_REVIEWER = "MODEL_REVISION_REVIEWER"
ROLE_REVISION_APPLIER = "MODEL_REVISION_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def proposal_to_dict(value: ModelRevisionProposal) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["proposed_positive_likelihood_bps"] = [[key, probability] for key, probability in value.proposed_positive_likelihood_bps]
    data["conditioning_evidence_hashes"] = list(value.conditioning_evidence_hashes)
    return data


def proposal_from_dict(data: Mapping[str, object]) -> ModelRevisionProposal:
    result = ModelRevisionProposal(
        proposal_ref=str(data["proposal_ref"]),
        candidate_hash=str(data["candidate_hash"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        calibration_family_ref=str(data["calibration_family_ref"]),
        calibration_snapshot_hash=str(data["calibration_snapshot_hash"]),
        base_distribution_hash=str(data["base_distribution_hash"]),
        base_model_hash=str(data["base_model_hash"]),
        model_ref=str(data["model_ref"]),
        base_model_generation=int(data["base_model_generation"]),
        proposed_model_generation=int(data["proposed_model_generation"]),
        proposed_positive_likelihood_bps=tuple((str(item[0]), int(item[1])) for item in data["proposed_positive_likelihood_bps"]),
        conditioning_evidence_hashes=tuple(str(value) for value in data.get("conditioning_evidence_hashes", [])),
        reason_ref=str(data["reason_ref"]),
        proposer_ref=str(data["proposer_ref"]),
        proposed_at=int(data["proposed_at"]),
        proposal_hash=str(data["proposal_hash"]),
    )
    result.validate()
    return result


def replay_case_to_dict(value: CounterfactualReplayCase) -> dict[str, object]:
    value.validate()
    return asdict(value)


def replay_to_dict(value: CounterfactualReplayReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["case_hashes"] = list(value.case_hashes)
    return data


def replay_from_dict(data: Mapping[str, object]) -> CounterfactualReplayReceipt:
    result = CounterfactualReplayReceipt(
        proposal_hash=str(data["proposal_hash"]),
        case_hashes=tuple(str(value) for value in data.get("case_hashes", [])),
        scored_case_count=int(data["scored_case_count"]),
        min_cases=int(data["min_cases"]),
        old_mean_brier_ppm=None if data.get("old_mean_brier_ppm") is None else int(data["old_mean_brier_ppm"]),
        proposed_mean_brier_ppm=None if data.get("proposed_mean_brier_ppm") is None else int(data["proposed_mean_brier_ppm"]),
        improvement_ppm=None if data.get("improvement_ppm") is None else int(data["improvement_ppm"]),
        status=str(data["status"]),
        replayed_at=int(data["replayed_at"]),
        replay_hash=str(data["replay_hash"]),
    )
    result.validate()
    return result


def review_to_dict(value: ModelRevisionReviewReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> ModelRevisionReviewReceipt:
    result = ModelRevisionReviewReceipt(
        proposal_hash=str(data["proposal_hash"]),
        replay_hash=str(data["replay_hash"]),
        decision=str(data["decision"]),
        rationale_ref=str(data["rationale_ref"]),
        proposer_ref=str(data["proposer_ref"]),
        reviewer_ref=str(data["reviewer_ref"]),
        reviewed_at=int(data["reviewed_at"]),
        review_hash=str(data["review_hash"]),
    )
    result.validate()
    return result


def revision_to_dict(value: ModelRevisionReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = calibration_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_revision_proposal (
            proposal_hash TEXT PRIMARY KEY,
            proposal_ref TEXT NOT NULL UNIQUE,
            candidate_hash TEXT NOT NULL,
            proposal_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_revision_replay (
            replay_hash TEXT PRIMARY KEY,
            proposal_hash TEXT NOT NULL UNIQUE,
            replay_json TEXT NOT NULL,
            cases_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_revision_review (
            review_hash TEXT PRIMARY KEY,
            proposal_hash TEXT NOT NULL UNIQUE,
            review_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_revision_history (
            revision_hash TEXT PRIMARY KEY,
            proposal_hash TEXT NOT NULL UNIQUE,
            candidate_hash TEXT NOT NULL,
            base_model_hash TEXT NOT NULL,
            new_model_hash TEXT NOT NULL,
            base_model_json TEXT NOT NULL,
            new_model_json TEXT NOT NULL,
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
        raise PermissionError("model revision authority failed: " + ",".join(dict.fromkeys(failures)))


def _proposal(conn: sqlite3.Connection, proposal_hash: str) -> ModelRevisionProposal:
    row = conn.execute("SELECT proposal_json FROM model_revision_proposal WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None:
        raise ValueError("unknown model revision proposal")
    return proposal_from_dict(json.loads(row[0]))


def _replay(conn: sqlite3.Connection, proposal_hash: str) -> CounterfactualReplayReceipt:
    row = conn.execute("SELECT replay_json FROM model_revision_replay WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None:
        raise ValueError("model revision replay is not recorded")
    return replay_from_dict(json.loads(row[0]))


def _review(conn: sqlite3.Connection, proposal_hash: str) -> ModelRevisionReviewReceipt:
    row = conn.execute("SELECT review_json FROM model_revision_review WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None:
        raise ValueError("model revision review is not recorded")
    return review_from_dict(json.loads(row[0]))


def _calibrations_for_proposal(conn: sqlite3.Connection, proposal: ModelRevisionProposal):
    rows = conn.execute(
        "SELECT receipt_json FROM calibration_likelihood_history WHERE family_ref=? AND model_ref=? ORDER BY calibration_hash",
        (proposal.calibration_family_ref, proposal.model_ref),
    ).fetchall()
    return tuple(likelihood_from_dict(json.loads(row[0])) for row in rows)


def _current_family_snapshot(conn: sqlite3.Connection, *, family_ref: str, min_samples: int, gap_threshold_bps: int, measured_at: int):
    state = calibration_state(
        conn,
        family_min_samples=min_samples,
        family_gap_threshold_bps=gap_threshold_bps,
        dependency_min_samples=8,
        dependency_threshold_bps=1000,
        measured_at=measured_at,
    )
    for item in state["family_snapshots"]:
        if item.calibration_family_ref == family_ref:
            return item
    raise ValueError("calibration family has no recorded observations")


def action_register_revision_proposal(value: ModelRevisionProposal) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_revision_proposal",
        "proposal_hash": value.proposal_hash,
        "candidate_hash": value.candidate_hash,
        "base_model_hash": value.base_model_hash,
        "calibration_snapshot_hash": value.calibration_snapshot_hash,
        "proposed_model_generation": value.proposed_model_generation,
    }


def action_record_revision_replay(value: CounterfactualReplayReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_counterfactual_replay",
        "proposal_hash": value.proposal_hash,
        "replay_hash": value.replay_hash,
        "case_hashes": list(value.case_hashes),
        "status": value.status,
    }


def action_record_revision_review(value: ModelRevisionReviewReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_revision_review",
        "proposal_hash": value.proposal_hash,
        "replay_hash": value.replay_hash,
        "review_hash": value.review_hash,
        "decision": value.decision,
    }


def action_apply_model_revision(value: ModelRevisionReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "apply_model_revision",
        "proposal_hash": value.proposal_hash,
        "replay_hash": value.replay_hash,
        "review_hash": value.review_hash,
        "revision_hash": value.revision_hash,
        "base_model_hash": value.base_model_hash,
        "new_model_hash": value.new_model_hash,
    }


def _register_proposal(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> ModelRevisionProposal:
    candidate_hash = str(payload["candidate_hash"])
    distribution = _distribution_for_candidate(conn, candidate_hash)
    model = _model(conn, candidate_hash)
    family_ref = str(payload["calibration_family_ref"])
    snapshot = _current_family_snapshot(
        conn,
        family_ref=family_ref,
        min_samples=int(payload.get("min_samples", 5)),
        gap_threshold_bps=int(payload.get("marginal_gap_threshold_bps", 1000)),
        measured_at=enforcement.now,
    )
    proposed_likelihoods = {str(key): int(value) for key, value in _mapping(payload["proposed_positive_likelihood_bps"], "proposed_positive_likelihood_bps").items()}
    proposal = make_model_revision_proposal(
        proposal_ref=str(payload["proposal_ref"]),
        distribution=distribution,
        base_model=model,
        calibration_snapshot=snapshot,
        proposed_positive_likelihood_bps=proposed_likelihoods,
        reason_ref=str(payload["reason_ref"]),
        proposer_ref=grant.subject_ref,
        proposed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_register_revision_proposal(proposal),
        required_role=ROLE_REVISION_PROPOSER,
        required_scope=verification_scope(distribution.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT proposal_json FROM model_revision_proposal WHERE proposal_ref=?", (proposal.proposal_ref,)).fetchone()
    if existing is not None:
        current = proposal_from_dict(json.loads(existing[0]))
        if current == proposal:
            return current
        raise ValueError("revision proposal_ref is immutable once registered")
    conn.execute(
        "INSERT INTO model_revision_proposal(proposal_hash,proposal_ref,candidate_hash,proposal_json) VALUES(?,?,?,?)",
        (proposal.proposal_hash, proposal.proposal_ref, proposal.candidate_hash, json.dumps(proposal_to_dict(proposal), sort_keys=True, separators=(",", ":"))),
    )
    return proposal


def _record_replay(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> tuple[tuple[CounterfactualReplayCase, ...], CounterfactualReplayReceipt]:
    proposal = _proposal(conn, str(payload["proposal_hash"]))
    cases, replay = replay_revision(
        proposal,
        _calibrations_for_proposal(conn, proposal),
        min_cases=int(payload.get("min_cases", 5)),
        replayed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_record_revision_replay(replay),
        required_role=ROLE_REVISION_REPLAY_KEEPER,
        required_scope=verification_scope(proposal.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT replay_json,cases_json FROM model_revision_replay WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    if existing is not None:
        current = replay_from_dict(json.loads(existing[0]))
        if current == replay:
            return cases, current
        raise ValueError("counterfactual replay already recorded; create a new proposal for a new replay")
    conn.execute(
        "INSERT INTO model_revision_replay(replay_hash,proposal_hash,replay_json,cases_json) VALUES(?,?,?,?)",
        (
            replay.replay_hash,
            proposal.proposal_hash,
            json.dumps(replay_to_dict(replay), sort_keys=True, separators=(",", ":")),
            json.dumps([replay_case_to_dict(item) for item in cases], sort_keys=True, separators=(",", ":")),
        ),
    )
    return cases, replay


def _record_review(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> ModelRevisionReviewReceipt:
    proposal = _proposal(conn, str(payload["proposal_hash"]))
    replay = _replay(conn, proposal.proposal_hash)
    review = review_revision(
        proposal,
        replay,
        decision=str(payload["decision"]),
        rationale_ref=str(payload["rationale_ref"]),
        reviewer_ref=grant.subject_ref,
        reviewed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_record_revision_review(review),
        required_role=ROLE_REVISION_REVIEWER,
        required_scope=verification_scope(proposal.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT review_json FROM model_revision_review WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    if existing is not None:
        current = review_from_dict(json.loads(existing[0]))
        if current == review:
            return current
        raise ValueError("revision review is immutable once recorded")
    conn.execute(
        "INSERT INTO model_revision_review(review_hash,proposal_hash,review_json) VALUES(?,?,?)",
        (review.review_hash, proposal.proposal_hash, json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":"))),
    )
    return review


def _same_replay_state(left: CounterfactualReplayReceipt, right: CounterfactualReplayReceipt) -> bool:
    return (
        left.proposal_hash == right.proposal_hash
        and left.case_hashes == right.case_hashes
        and left.scored_case_count == right.scored_case_count
        and left.min_cases == right.min_cases
        and left.old_mean_brier_ppm == right.old_mean_brier_ppm
        and left.proposed_mean_brier_ppm == right.proposed_mean_brier_ppm
        and left.improvement_ppm == right.improvement_ppm
        and left.status == right.status
    )


def _apply(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> tuple[object, ModelRevisionReceipt]:
    proposal = _proposal(conn, str(payload["proposal_hash"]))
    replay = _replay(conn, proposal.proposal_hash)
    review = _review(conn, proposal.proposal_hash)
    distribution = _distribution_for_candidate(conn, proposal.candidate_hash)
    current_model = _model(conn, proposal.candidate_hash)
    _, current_replay = replay_revision(
        proposal,
        _calibrations_for_proposal(conn, proposal),
        min_cases=replay.min_cases,
        replayed_at=enforcement.now,
    )
    if not _same_replay_state(replay, current_replay):
        raise ValueError("stale counterfactual replay; calibration history changed after review")
    new_model, revision = apply_revision(
        distribution=distribution,
        current_model=current_model,
        proposal=proposal,
        replay=replay,
        review=review,
        applied_at=enforcement.now,
        applier_ref=grant.subject_ref,
    )
    _enforce(
        grant,
        proof,
        action=action_apply_model_revision(revision),
        required_role=ROLE_REVISION_APPLIER,
        required_scope=verification_scope(proposal.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT revision_json FROM model_revision_history WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    if existing is not None:
        raise ValueError("model revision proposal has already been applied")
    base_json = json.dumps(model_to_dict(current_model), sort_keys=True, separators=(",", ":"))
    new_json = json.dumps(model_to_dict(new_model), sort_keys=True, separators=(",", ":"))
    conn.execute("UPDATE multi_likelihood_model SET model_json=? WHERE candidate_hash=?", (new_json, proposal.candidate_hash))
    conn.execute(
        "INSERT INTO model_revision_history(revision_hash,proposal_hash,candidate_hash,base_model_hash,new_model_hash,base_model_json,new_model_json,revision_json) VALUES(?,?,?,?,?,?,?,?)",
        (
            revision.revision_hash,
            proposal.proposal_hash,
            proposal.candidate_hash,
            current_model.model_hash,
            new_model.model_hash,
            base_json,
            new_json,
            json.dumps(revision_to_dict(revision), sort_keys=True, separators=(",", ":")),
        ),
    )
    return new_model, revision


def _state(conn: sqlite3.Connection) -> dict[str, object]:
    proposals = conn.execute("SELECT proposal_hash FROM model_revision_proposal ORDER BY proposal_hash").fetchall()
    replays = conn.execute("SELECT replay_hash FROM model_revision_replay ORDER BY replay_hash").fetchall()
    reviews = conn.execute("SELECT review_hash FROM model_revision_review ORDER BY review_hash").fetchall()
    revisions = conn.execute("SELECT revision_hash FROM model_revision_history ORDER BY revision_hash").fetchall()
    return {
        "proposal_hashes": [str(row[0]) for row in proposals],
        "replay_hashes": [str(row[0]) for row in replays],
        "review_hashes": [str(row[0]) for row in reviews],
        "revision_hashes": [str(row[0]) for row in revisions],
    }


def execute_revision_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != REVISION_PROTOCOL:
        raise ValueError("unsupported revision protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in REVISION_OPERATIONS:
        raise ValueError("unsupported revision operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_revision_state":
            return {"protocol": REVISION_PROTOCOL, "request_id": request_id, "ok": True, **_state(conn)}
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_revision_proposal":
            proposal = _register_proposal(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": REVISION_PROTOCOL, "request_id": request_id, "ok": True, "proposal": proposal_to_dict(proposal)}
        if operation == "record_counterfactual_replay":
            cases, replay = _record_replay(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": REVISION_PROTOCOL, "request_id": request_id, "ok": True, "replay": replay_to_dict(replay), "cases": [replay_case_to_dict(item) for item in cases]}
        if operation == "record_revision_review":
            review = _record_review(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": REVISION_PROTOCOL, "request_id": request_id, "ok": True, "review": review_to_dict(review)}
        new_model, revision = _apply(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
        conn.execute("COMMIT")
        return {"protocol": REVISION_PROTOCOL, "request_id": request_id, "ok": True, "new_model": model_to_dict(new_model), "revision": revision_to_dict(revision)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
