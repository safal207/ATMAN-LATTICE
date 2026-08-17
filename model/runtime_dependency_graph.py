from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.calibration import pair_from_dict, summarize_dependency_samples
from model.dependency_graph_revision import (
    DependencyGraphEdge,
    DependencyGraphRevisionReceipt,
    DependencyGraphState,
    StructuralGraphReplayReceipt,
    StructuralGraphReviewReceipt,
    StructuralGraphRevisionProposal,
    StructuralReplayCase,
    apply_structural_graph_revision,
    make_dependency_graph,
    make_dependency_graph_edge,
    make_structural_graph_revision_proposal,
    replay_structural_graph_revision,
    review_structural_graph_revision,
)
from model.enforcement import EnforcementContext
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_revision import _connect as revision_connect
from model.runtime_verification import verification_scope

GRAPH_PROTOCOL = "ATMAN-GRAPH/1.14"
GRAPH_OPERATIONS = {
    "register_dependency_graph",
    "register_graph_revision_proposal",
    "record_graph_revision_replay",
    "record_graph_revision_review",
    "apply_graph_revision",
    "get_graph_revision_state",
}

ROLE_GRAPH_BOOTSTRAP_KEEPER = "DEPENDENCY_GRAPH_BOOTSTRAP_KEEPER"
ROLE_GRAPH_REVISION_PROPOSER = "STRUCTURAL_GRAPH_REVISION_PROPOSER"
ROLE_GRAPH_REPLAY_KEEPER = "STRUCTURAL_GRAPH_REPLAY_KEEPER"
ROLE_GRAPH_REVISION_REVIEWER = "STRUCTURAL_GRAPH_REVISION_REVIEWER"
ROLE_GRAPH_REVISION_APPLIER = "STRUCTURAL_GRAPH_REVISION_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def edge_to_dict(value: DependencyGraphEdge) -> dict[str, object]:
    value.validate()
    return asdict(value)


def edge_from_dict(data: Mapping[str, object]) -> DependencyGraphEdge:
    result = DependencyGraphEdge(
        parent_model_ref=str(data["parent_model_ref"]),
        child_model_ref=str(data["child_model_ref"]),
        relation=str(data["relation"]),
        edge_hash=str(data["edge_hash"]),
    )
    result.validate()
    return result


def graph_to_dict(value: DependencyGraphState) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["edges"] = [edge_to_dict(edge) for edge in value.edges]
    return data


def graph_from_dict(data: Mapping[str, object]) -> DependencyGraphState:
    result = DependencyGraphState(
        graph_ref=str(data["graph_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        generation=int(data["generation"]),
        edges=tuple(edge_from_dict(_mapping(item, "edge")) for item in data.get("edges", [])),
        evidence_state_hash=str(data["evidence_state_hash"]),
        graph_hash=str(data["graph_hash"]),
    )
    result.validate()
    return result


def proposal_to_dict(value: StructuralGraphRevisionProposal) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["proposed_edges"] = [edge_to_dict(edge) for edge in value.proposed_edges]
    return data


def proposal_from_dict(data: Mapping[str, object]) -> StructuralGraphRevisionProposal:
    result = StructuralGraphRevisionProposal(
        proposal_ref=str(data["proposal_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        pair_key=str(data["pair_key"]),
        calibration_snapshot_hash=str(data["calibration_snapshot_hash"]),
        base_graph_hash=str(data["base_graph_hash"]),
        base_generation=int(data["base_generation"]),
        proposed_generation=int(data["proposed_generation"]),
        direction=str(data["direction"]),
        change_kind=str(data["change_kind"]),
        parent_model_ref=str(data["parent_model_ref"]),
        child_model_ref=str(data["child_model_ref"]),
        proposed_edges=tuple(edge_from_dict(_mapping(item, "edge")) for item in data.get("proposed_edges", [])),
        reason_ref=str(data["reason_ref"]),
        proposer_ref=str(data["proposer_ref"]),
        proposed_at=int(data["proposed_at"]),
        proposal_hash=str(data["proposal_hash"]),
    )
    result.validate()
    return result


def replay_case_to_dict(value: StructuralReplayCase) -> dict[str, object]:
    value.validate()
    return asdict(value)


def replay_to_dict(value: StructuralGraphReplayReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["sample_hashes"] = list(value.sample_hashes)
    data["case_hashes"] = list(value.case_hashes)
    return data


def replay_from_dict(data: Mapping[str, object]) -> StructuralGraphReplayReceipt:
    result = StructuralGraphReplayReceipt(
        proposal_hash=str(data["proposal_hash"]),
        sample_hashes=tuple(str(value) for value in data.get("sample_hashes", [])),
        case_hashes=tuple(str(value) for value in data.get("case_hashes", [])),
        scored_case_count=int(data["scored_case_count"]),
        min_cases=int(data["min_cases"]),
        base_mean_brier_ppm=None if data.get("base_mean_brier_ppm") is None else int(data["base_mean_brier_ppm"]),
        proposed_mean_brier_ppm=None if data.get("proposed_mean_brier_ppm") is None else int(data["proposed_mean_brier_ppm"]),
        improvement_ppm=None if data.get("improvement_ppm") is None else int(data["improvement_ppm"]),
        status=str(data["status"]),
        replayed_at=int(data["replayed_at"]),
        replay_hash=str(data["replay_hash"]),
    )
    result.validate()
    return result


def review_to_dict(value: StructuralGraphReviewReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> StructuralGraphReviewReceipt:
    result = StructuralGraphReviewReceipt(
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


def revision_to_dict(value: DependencyGraphRevisionReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = revision_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dependency_graph_current (
            subject_identity_ref TEXT PRIMARY KEY,
            graph_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dependency_graph_revision_proposal (
            proposal_hash TEXT PRIMARY KEY,
            proposal_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            proposal_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dependency_graph_revision_replay (
            replay_hash TEXT PRIMARY KEY,
            proposal_hash TEXT NOT NULL UNIQUE,
            replay_json TEXT NOT NULL,
            cases_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dependency_graph_revision_review (
            review_hash TEXT PRIMARY KEY,
            proposal_hash TEXT NOT NULL UNIQUE,
            review_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dependency_graph_revision_history (
            revision_hash TEXT PRIMARY KEY,
            proposal_hash TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            base_graph_hash TEXT NOT NULL,
            new_graph_hash TEXT NOT NULL,
            base_graph_json TEXT NOT NULL,
            new_graph_json TEXT NOT NULL,
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
        raise PermissionError("dependency graph authority failed: " + ",".join(dict.fromkeys(failures)))


def _graph(conn: sqlite3.Connection, subject_identity_ref: str) -> DependencyGraphState:
    row = conn.execute("SELECT graph_json FROM dependency_graph_current WHERE subject_identity_ref=?", (subject_identity_ref,)).fetchone()
    if row is None:
        raise ValueError("dependency graph is not initialized for subject")
    return graph_from_dict(json.loads(row[0]))


def _proposal(conn: sqlite3.Connection, proposal_hash: str) -> StructuralGraphRevisionProposal:
    row = conn.execute("SELECT proposal_json FROM dependency_graph_revision_proposal WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None:
        raise ValueError("unknown structural graph proposal")
    return proposal_from_dict(json.loads(row[0]))


def _replay(conn: sqlite3.Connection, proposal_hash: str) -> StructuralGraphReplayReceipt:
    row = conn.execute("SELECT replay_json FROM dependency_graph_revision_replay WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None:
        raise ValueError("structural graph replay is not recorded")
    return replay_from_dict(json.loads(row[0]))


def _review(conn: sqlite3.Connection, proposal_hash: str) -> StructuralGraphReviewReceipt:
    row = conn.execute("SELECT review_json FROM dependency_graph_revision_review WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None:
        raise ValueError("structural graph review is not recorded")
    return review_from_dict(json.loads(row[0]))


def _pair_samples(conn: sqlite3.Connection, pair_key: str):
    rows = conn.execute("SELECT receipt_json FROM calibration_dependency_pair WHERE pair_key=? ORDER BY sample_hash", (pair_key,)).fetchall()
    if not rows:
        raise ValueError("structural graph revision requires calibration dependency-pair history")
    return tuple(pair_from_dict(json.loads(row[0])) for row in rows)


def action_register_graph(value: DependencyGraphState) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_dependency_graph",
        "subject_identity_ref": value.subject_identity_ref,
        "graph_hash": value.graph_hash,
        "generation": value.generation,
    }


def action_register_graph_revision_proposal(value: StructuralGraphRevisionProposal) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_graph_revision_proposal",
        "proposal_hash": value.proposal_hash,
        "base_graph_hash": value.base_graph_hash,
        "pair_key": value.pair_key,
        "direction": value.direction,
        "change_kind": value.change_kind,
    }


def action_record_graph_revision_replay(value: StructuralGraphReplayReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_graph_revision_replay",
        "proposal_hash": value.proposal_hash,
        "replay_hash": value.replay_hash,
        "sample_hashes": list(value.sample_hashes),
        "status": value.status,
    }


def action_record_graph_revision_review(value: StructuralGraphReviewReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_graph_revision_review",
        "proposal_hash": value.proposal_hash,
        "replay_hash": value.replay_hash,
        "review_hash": value.review_hash,
        "decision": value.decision,
    }


def action_apply_graph_revision(value: DependencyGraphRevisionReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "apply_graph_revision",
        "proposal_hash": value.proposal_hash,
        "replay_hash": value.replay_hash,
        "review_hash": value.review_hash,
        "revision_hash": value.revision_hash,
        "base_graph_hash": value.base_graph_hash,
        "new_graph_hash": value.new_graph_hash,
    }


def _register_graph(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> DependencyGraphState:
    subject = str(payload["subject_identity_ref"])
    edges = tuple(
        make_dependency_graph_edge(str(_mapping(item, "edge")["parent_model_ref"]), str(_mapping(item, "edge")["child_model_ref"]))
        for item in payload.get("edges", [])
    )
    graph = make_dependency_graph(
        str(payload["graph_ref"]),
        subject_identity_ref=subject,
        generation=0,
        edges=edges,
        evidence_state_hash=str(payload["evidence_state_hash"]),
    )
    _enforce(
        grant,
        proof,
        action=action_register_graph(graph),
        required_role=ROLE_GRAPH_BOOTSTRAP_KEEPER,
        required_scope=verification_scope(subject),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT graph_json FROM dependency_graph_current WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = graph_from_dict(json.loads(row[0]))
        if current == graph:
            return current
        raise ValueError("dependency graph bootstrap is immutable once initialized")
    conn.execute("INSERT INTO dependency_graph_current(subject_identity_ref,graph_json) VALUES(?,?)", (subject, json.dumps(graph_to_dict(graph), sort_keys=True, separators=(",", ":"))))
    return graph


def _register_proposal(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> StructuralGraphRevisionProposal:
    subject = str(payload["subject_identity_ref"])
    base_graph = _graph(conn, subject)
    pair_key = str(payload["pair_key"])
    samples = _pair_samples(conn, pair_key)
    snapshot = summarize_dependency_samples(
        samples,
        min_samples=int(payload.get("min_samples", 8)),
        dependency_threshold_bps=int(payload.get("dependency_threshold_bps", 1000)),
        measured_at=enforcement.now,
    )
    proposal = make_structural_graph_revision_proposal(
        proposal_ref=str(payload["proposal_ref"]),
        base_graph=base_graph,
        calibration_snapshot=snapshot,
        samples=samples,
        direction=str(payload["direction"]),
        reason_ref=str(payload["reason_ref"]),
        proposer_ref=grant.subject_ref,
        proposed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_register_graph_revision_proposal(proposal),
        required_role=ROLE_GRAPH_REVISION_PROPOSER,
        required_scope=verification_scope(subject),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT proposal_json FROM dependency_graph_revision_proposal WHERE proposal_ref=?", (proposal.proposal_ref,)).fetchone()
    if row is not None:
        current = proposal_from_dict(json.loads(row[0]))
        if current == proposal:
            return current
        raise ValueError("structural graph proposal_ref is immutable once registered")
    conn.execute(
        "INSERT INTO dependency_graph_revision_proposal(proposal_hash,proposal_ref,subject_identity_ref,pair_key,proposal_json) VALUES(?,?,?,?,?)",
        (proposal.proposal_hash, proposal.proposal_ref, subject, pair_key, json.dumps(proposal_to_dict(proposal), sort_keys=True, separators=(",", ":"))),
    )
    return proposal


def _record_replay(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    proposal = _proposal(conn, str(payload["proposal_hash"]))
    base_graph = _graph(conn, proposal.subject_identity_ref)
    if base_graph.graph_hash != proposal.base_graph_hash:
        raise ValueError("structural proposal base graph is already stale")
    cases, replay = replay_structural_graph_revision(
        proposal,
        base_graph,
        _pair_samples(conn, proposal.pair_key),
        min_cases=int(payload.get("min_cases", 6)),
        replayed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_record_graph_revision_replay(replay),
        required_role=ROLE_GRAPH_REPLAY_KEEPER,
        required_scope=verification_scope(proposal.subject_identity_ref),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT replay_json FROM dependency_graph_revision_replay WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    if row is not None:
        current = replay_from_dict(json.loads(row[0]))
        if current == replay:
            return cases, current
        raise ValueError("structural graph replay already recorded; create a new proposal for new evidence")
    conn.execute(
        "INSERT INTO dependency_graph_revision_replay(replay_hash,proposal_hash,replay_json,cases_json) VALUES(?,?,?,?)",
        (replay.replay_hash, proposal.proposal_hash, json.dumps(replay_to_dict(replay), sort_keys=True, separators=(",", ":")), json.dumps([replay_case_to_dict(item) for item in cases], sort_keys=True, separators=(",", ":"))),
    )
    return cases, replay


def _record_review(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> StructuralGraphReviewReceipt:
    proposal = _proposal(conn, str(payload["proposal_hash"]))
    replay = _replay(conn, proposal.proposal_hash)
    review = review_structural_graph_revision(
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
        action=action_record_graph_revision_review(review),
        required_role=ROLE_GRAPH_REVISION_REVIEWER,
        required_scope=verification_scope(proposal.subject_identity_ref),
        enforcement=enforcement,
    )
    row = conn.execute("SELECT review_json FROM dependency_graph_revision_review WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    if row is not None:
        current = review_from_dict(json.loads(row[0]))
        if current == review:
            return current
        raise ValueError("structural graph review is immutable once recorded")
    conn.execute("INSERT INTO dependency_graph_revision_review(review_hash,proposal_hash,review_json) VALUES(?,?,?)", (review.review_hash, proposal.proposal_hash, json.dumps(review_to_dict(review), sort_keys=True, separators=(",", ":"))))
    return review


def _same_replay_state(left: StructuralGraphReplayReceipt, right: StructuralGraphReplayReceipt) -> bool:
    return (
        left.proposal_hash == right.proposal_hash
        and left.sample_hashes == right.sample_hashes
        and left.case_hashes == right.case_hashes
        and left.scored_case_count == right.scored_case_count
        and left.min_cases == right.min_cases
        and left.base_mean_brier_ppm == right.base_mean_brier_ppm
        and left.proposed_mean_brier_ppm == right.proposed_mean_brier_ppm
        and left.improvement_ppm == right.improvement_ppm
        and left.status == right.status
    )


def _apply(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext):
    proposal = _proposal(conn, str(payload["proposal_hash"]))
    replay = _replay(conn, proposal.proposal_hash)
    review = _review(conn, proposal.proposal_hash)
    current_graph = _graph(conn, proposal.subject_identity_ref)
    _, fresh_replay = replay_structural_graph_revision(
        proposal,
        current_graph,
        _pair_samples(conn, proposal.pair_key),
        min_cases=replay.min_cases,
        replayed_at=enforcement.now,
    )
    if not _same_replay_state(replay, fresh_replay):
        raise ValueError("stale structural replay; dependency calibration history changed after review")
    new_graph, revision = apply_structural_graph_revision(
        current_graph=current_graph,
        proposal=proposal,
        replay=replay,
        review=review,
        applier_ref=grant.subject_ref,
        applied_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_apply_graph_revision(revision),
        required_role=ROLE_GRAPH_REVISION_APPLIER,
        required_scope=verification_scope(proposal.subject_identity_ref),
        enforcement=enforcement,
    )
    if conn.execute("SELECT 1 FROM dependency_graph_revision_history WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone() is not None:
        raise ValueError("structural graph proposal has already been applied")
    base_json = json.dumps(graph_to_dict(current_graph), sort_keys=True, separators=(",", ":"))
    new_json = json.dumps(graph_to_dict(new_graph), sort_keys=True, separators=(",", ":"))
    conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?", (new_json, proposal.subject_identity_ref))
    conn.execute(
        "INSERT INTO dependency_graph_revision_history(revision_hash,proposal_hash,subject_identity_ref,base_graph_hash,new_graph_hash,base_graph_json,new_graph_json,revision_json) VALUES(?,?,?,?,?,?,?,?)",
        (revision.revision_hash, proposal.proposal_hash, proposal.subject_identity_ref, current_graph.graph_hash, new_graph.graph_hash, base_json, new_json, json.dumps(revision_to_dict(revision), sort_keys=True, separators=(",", ":"))),
    )
    return new_graph, revision


def _state(conn: sqlite3.Connection) -> dict[str, object]:
    graph_rows = conn.execute("SELECT graph_json FROM dependency_graph_current ORDER BY subject_identity_ref").fetchall()
    proposals = conn.execute("SELECT proposal_hash FROM dependency_graph_revision_proposal ORDER BY proposal_hash").fetchall()
    replays = conn.execute("SELECT replay_hash FROM dependency_graph_revision_replay ORDER BY replay_hash").fetchall()
    reviews = conn.execute("SELECT review_hash FROM dependency_graph_revision_review ORDER BY review_hash").fetchall()
    revisions = conn.execute("SELECT revision_hash FROM dependency_graph_revision_history ORDER BY revision_hash").fetchall()
    return {
        "graphs": [graph_to_dict(graph_from_dict(json.loads(row[0]))) for row in graph_rows],
        "proposal_hashes": [str(row[0]) for row in proposals],
        "replay_hashes": [str(row[0]) for row in replays],
        "review_hashes": [str(row[0]) for row in reviews],
        "revision_hashes": [str(row[0]) for row in revisions],
    }


def execute_graph_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != GRAPH_PROTOCOL:
        raise ValueError("unsupported dependency graph protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in GRAPH_OPERATIONS:
        raise ValueError("unsupported dependency graph operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_graph_revision_state":
            return {"protocol": GRAPH_PROTOCOL, "request_id": request_id, "ok": True, **_state(conn)}
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_dependency_graph":
            graph = _register_graph(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": GRAPH_PROTOCOL, "request_id": request_id, "ok": True, "graph": graph_to_dict(graph)}
        if operation == "register_graph_revision_proposal":
            proposal = _register_proposal(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": GRAPH_PROTOCOL, "request_id": request_id, "ok": True, "proposal": proposal_to_dict(proposal)}
        if operation == "record_graph_revision_replay":
            cases, replay = _record_replay(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": GRAPH_PROTOCOL, "request_id": request_id, "ok": True, "replay": replay_to_dict(replay), "cases": [replay_case_to_dict(item) for item in cases]}
        if operation == "record_graph_revision_review":
            review = _record_review(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": GRAPH_PROTOCOL, "request_id": request_id, "ok": True, "review": review_to_dict(review)}
        graph, revision = _apply(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
        conn.execute("COMMIT")
        return {"protocol": GRAPH_PROTOCOL, "request_id": request_id, "ok": True, "graph": graph_to_dict(graph), "revision": revision_to_dict(revision)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
