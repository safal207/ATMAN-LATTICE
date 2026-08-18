from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.remediation import (
    DriftRemediationProposal,
    RemediationAssessmentReceipt,
    RemediationExecutionReceipt,
    RemediationPolicy,
    RemediationReviewReceipt,
    RemediationSelectionReceipt,
    assess_remediation_proposal,
    execute_remediation,
    make_remediation_policy,
    make_remediation_proposal,
    review_remediation_selection,
    select_remediation,
)
from model.replication import ReplicationSeriesSnapshot, summarize_replication_series
from model.runtime_dependency_graph import _graph, graph_from_dict, graph_to_dict
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_replication import (
    _confirmed_bundle,
    _connect as replication_connect,
    _policy as replication_policy,
    _target,
    evaluation_from_dict as replication_evaluation_from_dict,
    review_from_dict as replication_review_from_dict,
)
from model.runtime_verification import verification_scope

REMEDIATION_PROTOCOL = "ATMAN-REMEDIATE/1.19"
REMEDIATION_OPERATIONS = {
    "register_remediation_policy",
    "register_remediation_proposal",
    "assess_remediation_proposal",
    "select_remediation",
    "record_remediation_review",
    "apply_remediation",
    "get_remediation_state",
}

ROLE_REMEDIATION_POLICY_KEEPER = "REMEDIATION_POLICY_KEEPER"
ROLE_REMEDIATION_PROPOSER = "REMEDIATION_PROPOSER"
ROLE_REMEDIATION_ASSESSOR = "REMEDIATION_ASSESSOR"
ROLE_REMEDIATION_SELECTOR = "REMEDIATION_SELECTOR"
ROLE_REMEDIATION_REVIEWER = "REMEDIATION_REVIEWER"
ROLE_REMEDIATION_APPLIER = "REMEDIATION_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def policy_to_dict(value: RemediationPolicy) -> dict[str, object]:
    value.validate(); data = asdict(value); data["allowed_actions"] = list(value.allowed_actions); return data


def policy_from_dict(data: Mapping[str, object]) -> RemediationPolicy:
    result = RemediationPolicy(
        policy_ref=str(data["policy_ref"]), subject_identity_ref=str(data["subject_identity_ref"]),
        allowed_actions=tuple(str(v) for v in data.get("allowed_actions", [])),
        rollback_requires_nonpositive_improvement=bool(data["rollback_requires_nonpositive_improvement"]),
        registered_at=int(data["registered_at"]), policy_hash=str(data["policy_hash"]),
    )
    result.validate(); return result


def proposal_to_dict(value: DriftRemediationProposal) -> dict[str, object]:
    value.validate(); return asdict(value)


def proposal_from_dict(data: Mapping[str, object]) -> DriftRemediationProposal:
    result = DriftRemediationProposal(
        proposal_ref=str(data["proposal_ref"]), subject_identity_ref=str(data["subject_identity_ref"]), target_hash=str(data["target_hash"]),
        snapshot_hash=str(data["snapshot_hash"]), latest_evaluation_hash=str(data["latest_evaluation_hash"]),
        confirmed_revision_hash=str(data["confirmed_revision_hash"]), current_graph_hash=str(data["current_graph_hash"]),
        current_generation=int(data["current_generation"]), rollback_graph_hash=str(data["rollback_graph_hash"]), rollback_generation=int(data["rollback_generation"]),
        action=str(data["action"]), downstream_protocol=None if data.get("downstream_protocol") is None else str(data["downstream_protocol"]),
        drift_kind=str(data["drift_kind"]), reason_ref=str(data["reason_ref"]), proposer_ref=str(data["proposer_ref"]),
        proposed_at=int(data["proposed_at"]), proposal_hash=str(data["proposal_hash"]),
    )
    result.validate(); return result


def assessment_to_dict(value: RemediationAssessmentReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def assessment_from_dict(data: Mapping[str, object]) -> RemediationAssessmentReceipt:
    result = RemediationAssessmentReceipt(
        proposal_hash=str(data["proposal_hash"]), snapshot_hash=str(data["snapshot_hash"]), latest_evaluation_hash=str(data["latest_evaluation_hash"]),
        action=str(data["action"]), latest_regularized_improvement_ppm=int(data["latest_regularized_improvement_ppm"]),
        latest_confirmed_mean_brier_ppm=int(data["latest_confirmed_mean_brier_ppm"]), baseline_confirmed_mean_brier_ppm=int(data["baseline_confirmed_mean_brier_ppm"]),
        latest_drift_kind=str(data["latest_drift_kind"]), status=str(data["status"]),
        rollback_margin_ppm=None if data.get("rollback_margin_ppm") is None else int(data["rollback_margin_ppm"]),
        proposer_ref=str(data["proposer_ref"]), latest_evaluator_ref=str(data["latest_evaluator_ref"]), assessor_ref=str(data["assessor_ref"]),
        assessed_at=int(data["assessed_at"]), assessment_hash=str(data["assessment_hash"]),
    )
    result.validate(); return result


def selection_to_dict(value: RemediationSelectionReceipt) -> dict[str, object]:
    value.validate(); data = asdict(value); data["proposal_hashes"] = list(value.proposal_hashes); data["assessment_hashes"] = list(value.assessment_hashes); return data


def selection_from_dict(data: Mapping[str, object]) -> RemediationSelectionReceipt:
    result = RemediationSelectionReceipt(
        selection_ref=str(data["selection_ref"]), snapshot_hash=str(data["snapshot_hash"]),
        proposal_hashes=tuple(str(v) for v in data.get("proposal_hashes", [])), assessment_hashes=tuple(str(v) for v in data.get("assessment_hashes", [])),
        selected_proposal_hash=str(data["selected_proposal_hash"]), selected_assessment_hash=str(data["selected_assessment_hash"]),
        selected_action=str(data["selected_action"]), selected_status=str(data["selected_status"]), selected_proposer_ref=str(data["selected_proposer_ref"]),
        selected_assessor_ref=str(data["selected_assessor_ref"]), selector_ref=str(data["selector_ref"]), selected_at=int(data["selected_at"]),
        selection_hash=str(data["selection_hash"]),
    )
    result.validate(); return result


def review_to_dict(value: RemediationReviewReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def review_from_dict(data: Mapping[str, object]) -> RemediationReviewReceipt:
    result = RemediationReviewReceipt(
        selection_hash=str(data["selection_hash"]), snapshot_hash=str(data["snapshot_hash"]), selected_proposal_hash=str(data["selected_proposal_hash"]),
        selected_assessment_hash=str(data["selected_assessment_hash"]), selected_action=str(data["selected_action"]), decision=str(data["decision"]),
        rationale_ref=str(data["rationale_ref"]), proposer_ref=str(data["proposer_ref"]), assessor_ref=str(data["assessor_ref"]),
        selector_ref=str(data["selector_ref"]), reviewer_ref=str(data["reviewer_ref"]), reviewed_at=int(data["reviewed_at"]), review_hash=str(data["review_hash"]),
    )
    result.validate(); return result


def execution_to_dict(value: RemediationExecutionReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def snapshot_from_dict(data: Mapping[str, object]) -> ReplicationSeriesSnapshot:
    result = ReplicationSeriesSnapshot(
        target_hash=str(data["target_hash"]), policy_hash=str(data["policy_hash"]),
        evaluation_hashes=tuple(str(v) for v in data.get("evaluation_hashes", [])), review_hashes=tuple(str(v) for v in data.get("review_hashes", [])),
        latest_generation=int(data["latest_generation"]), replication_count=int(data["replication_count"]), stable_count=int(data["stable_count"]),
        drift_count=int(data["drift_count"]), consecutive_drift_count=int(data["consecutive_drift_count"]), persistent_drift_epochs=int(data["persistent_drift_epochs"]),
        latest_status=str(data["latest_status"]), signal=str(data["signal"]), measured_at=int(data["measured_at"]), snapshot_hash=str(data["snapshot_hash"]),
    )
    result.validate(); return result


def _connect(db_path: str) -> sqlite3.Connection:
    conn = replication_connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS remediation_policy (subject_identity_ref TEXT PRIMARY KEY, policy_ref TEXT NOT NULL UNIQUE, policy_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS remediation_proposal (proposal_hash TEXT PRIMARY KEY, proposal_ref TEXT NOT NULL UNIQUE, snapshot_hash TEXT NOT NULL, target_hash TEXT NOT NULL, action TEXT NOT NULL, proposal_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS remediation_assessment (assessment_hash TEXT PRIMARY KEY, proposal_hash TEXT NOT NULL UNIQUE, snapshot_hash TEXT NOT NULL, assessment_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS remediation_selection (selection_hash TEXT PRIMARY KEY, selection_ref TEXT NOT NULL UNIQUE, snapshot_hash TEXT NOT NULL UNIQUE, selection_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS remediation_review (review_hash TEXT PRIMARY KEY, selection_hash TEXT NOT NULL UNIQUE, review_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS remediation_execution (execution_hash TEXT PRIMARY KEY, snapshot_hash TEXT NOT NULL UNIQUE, selection_hash TEXT NOT NULL UNIQUE, action TEXT NOT NULL, old_graph_hash TEXT NOT NULL, new_graph_hash TEXT NOT NULL, old_graph_json TEXT NOT NULL, new_graph_json TEXT NOT NULL, proposal_json TEXT NOT NULL, assessment_json TEXT NOT NULL, selection_json TEXT NOT NULL, review_json TEXT NOT NULL, execution_json TEXT NOT NULL)""")
    return conn


def _enforce(grant: AuthorityGrant, proof: AuthorityProof, *, action: object, required_role: str, required_scope: str, enforcement: EnforcementContext) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(grant, proof, action=action, trusted_issuer_keys=enforcement.trusted_issuer_keys, current_policy_generation=enforcement.policy_generation, now=enforcement.now)
    failures = list(limitations)
    if proof.role != required_role: failures.append("required_role_mismatch")
    if proof.scope != required_scope: failures.append("required_scope_mismatch")
    if not valid or failures: raise PermissionError("remediation authority failed: " + ",".join(dict.fromkeys(failures)))


def _policy(conn: sqlite3.Connection, subject: str) -> RemediationPolicy:
    row = conn.execute("SELECT policy_json FROM remediation_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is None: raise ValueError("remediation policy is not registered")
    return policy_from_dict(json.loads(row[0]))


def _proposal(conn: sqlite3.Connection, proposal_hash: str) -> DriftRemediationProposal:
    row = conn.execute("SELECT proposal_json FROM remediation_proposal WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None: raise ValueError("unknown remediation proposal")
    return proposal_from_dict(json.loads(row[0]))


def _assessment(conn: sqlite3.Connection, proposal_hash: str) -> RemediationAssessmentReceipt:
    row = conn.execute("SELECT assessment_json FROM remediation_assessment WHERE proposal_hash=?", (proposal_hash,)).fetchone()
    if row is None: raise ValueError("remediation proposal has not been assessed")
    return assessment_from_dict(json.loads(row[0]))


def _selection(conn: sqlite3.Connection, selection_hash: str) -> RemediationSelectionReceipt:
    row = conn.execute("SELECT selection_json FROM remediation_selection WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None: raise ValueError("unknown remediation selection")
    return selection_from_dict(json.loads(row[0]))


def _review(conn: sqlite3.Connection, selection_hash: str) -> RemediationReviewReceipt:
    row = conn.execute("SELECT review_json FROM remediation_review WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None: raise ValueError("remediation selection has not been reviewed")
    return review_from_dict(json.loads(row[0]))


def _snapshot(conn: sqlite3.Connection, snapshot_hash: str) -> ReplicationSeriesSnapshot:
    row = conn.execute("SELECT snapshot_json FROM replication_snapshot WHERE snapshot_hash=?", (snapshot_hash,)).fetchone()
    if row is None: raise ValueError("unknown replication snapshot")
    return snapshot_from_dict(json.loads(row[0]))


def _fresh_snapshot(conn: sqlite3.Connection, snapshot_hash: str) -> ReplicationSeriesSnapshot:
    snapshot = _snapshot(conn, snapshot_hash)
    target = _target(conn, snapshot.target_hash)
    policy = replication_policy(conn, target.subject_identity_ref)
    eval_rows = conn.execute("SELECT evaluation_json FROM replication_evaluation WHERE target_hash=?", (target.target_hash,)).fetchall()
    evaluations = tuple(replication_evaluation_from_dict(json.loads(row[0])) for row in eval_rows)
    reviews = []
    for evaluation in evaluations:
        row = conn.execute("SELECT review_json FROM replication_review WHERE evaluation_hash=?", (evaluation.evaluation_hash,)).fetchone()
        if row is None: raise ValueError("current replication state contains unreviewed evaluation")
        reviews.append(replication_review_from_dict(json.loads(row[0])))
    fresh = summarize_replication_series(evaluations=evaluations, reviews=tuple(reviews), policy=policy, measured_at=snapshot.measured_at)
    if fresh != snapshot:
        raise ValueError("stale remediation snapshot: replication history changed")
    if fresh.signal != "PERSISTENT_DRIFT_SIGNAL":
        raise ValueError("remediation requires current PERSISTENT_DRIFT_SIGNAL")
    return fresh


def _latest_evaluation(conn: sqlite3.Connection, snapshot: ReplicationSeriesSnapshot):
    row = conn.execute("SELECT evaluation_json FROM replication_evaluation WHERE evaluation_hash=?", (snapshot.evaluation_hashes[-1],)).fetchone()
    if row is None: raise ValueError("latest replication evaluation is missing")
    return replication_evaluation_from_dict(json.loads(row[0]))


def _proposal_set(conn: sqlite3.Connection, snapshot_hash: str) -> tuple[DriftRemediationProposal, ...]:
    rows = conn.execute("SELECT proposal_json FROM remediation_proposal WHERE snapshot_hash=? ORDER BY proposal_hash", (snapshot_hash,)).fetchall()
    return tuple(proposal_from_dict(json.loads(row[0])) for row in rows)


def _assessment_set(conn: sqlite3.Connection, proposals: tuple[DriftRemediationProposal, ...]) -> tuple[RemediationAssessmentReceipt, ...]:
    result = []
    for proposal in proposals:
        result.append(_assessment(conn, proposal.proposal_hash))
    return tuple(result)


def _fresh_selection(conn: sqlite3.Connection, selection: RemediationSelectionReceipt) -> tuple[RemediationSelectionReceipt, ReplicationSeriesSnapshot]:
    snapshot = _fresh_snapshot(conn, selection.snapshot_hash)
    proposals = _proposal_set(conn, snapshot.snapshot_hash)
    assessments = _assessment_set(conn, proposals)
    fresh = select_remediation(
        selection_ref=selection.selection_ref, snapshot=snapshot, proposals=proposals, assessments=assessments,
        selected_proposal_hash=selection.selected_proposal_hash, selector_ref=selection.selector_ref, selected_at=selection.selected_at,
    )
    if fresh != selection:
        raise ValueError("stale remediation selection: candidate set changed")
    return fresh, snapshot


def action_register_policy(value: RemediationPolicy) -> dict[str, object]:
    value.validate(); return {"operation":"register_remediation_policy","subject_identity_ref":value.subject_identity_ref,"policy_hash":value.policy_hash,"allowed_actions":list(value.allowed_actions)}


def action_proposal(value: DriftRemediationProposal) -> dict[str, object]:
    value.validate(); return {"operation":"register_remediation_proposal","proposal_hash":value.proposal_hash,"snapshot_hash":value.snapshot_hash,"action":value.action,"current_graph_hash":value.current_graph_hash}


def action_assessment(value: RemediationAssessmentReceipt) -> dict[str, object]:
    value.validate(); return {"operation":"assess_remediation_proposal","proposal_hash":value.proposal_hash,"assessment_hash":value.assessment_hash,"status":value.status}


def action_selection(value: RemediationSelectionReceipt) -> dict[str, object]:
    value.validate(); return {"operation":"select_remediation","selection_hash":value.selection_hash,"snapshot_hash":value.snapshot_hash,"selected_proposal_hash":value.selected_proposal_hash,"selected_action":value.selected_action}


def action_review(value: RemediationReviewReceipt) -> dict[str, object]:
    value.validate(); return {"operation":"record_remediation_review","selection_hash":value.selection_hash,"review_hash":value.review_hash,"decision":value.decision}


def action_apply(value: RemediationExecutionReceipt) -> dict[str, object]:
    value.validate(); return {"operation":"apply_remediation","execution_hash":value.execution_hash,"snapshot_hash":value.snapshot_hash,"action":value.action,"old_graph_hash":value.old_graph_hash,"new_graph_hash":value.new_graph_hash}


def _register_policy(conn, payload, *, grant, proof, enforcement):
    subject = str(payload["subject_identity_ref"])
    allowed = tuple(str(v) for v in payload.get("allowed_actions", [])) or ("COLLECT_MORE_DATA","HOLD","PARAMETER_REVISION","SAFE_ROLLBACK","STRUCTURAL_REVISION")
    value = make_remediation_policy(
        policy_ref=str(payload["policy_ref"]), subject_identity_ref=subject, allowed_actions=allowed,
        rollback_requires_nonpositive_improvement=bool(payload.get("rollback_requires_nonpositive_improvement", True)), registered_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_register_policy(value), required_role=ROLE_REMEDIATION_POLICY_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT policy_json FROM remediation_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = policy_from_dict(json.loads(row[0]))
        if current == value: return current
        raise ValueError("remediation policy is immutable once registered")
    conn.execute("INSERT INTO remediation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (subject,value.policy_ref,json.dumps(policy_to_dict(value),sort_keys=True,separators=(",",":"))))
    return value


def _register_proposal(conn, payload, *, grant, proof, enforcement):
    snapshot = _fresh_snapshot(conn, str(payload["snapshot_hash"])); target = _target(conn, snapshot.target_hash); policy = _policy(conn, target.subject_identity_ref)
    base_graph, confirmed_graph, _, _, _, _, _ = _confirmed_bundle(conn, target.confirmed_revision_hash)
    current_graph = _graph(conn, target.subject_identity_ref)
    if current_graph.graph_hash != confirmed_graph.graph_hash:
        raise ValueError("replication target no longer represents current graph")
    latest = _latest_evaluation(conn, snapshot)
    value = make_remediation_proposal(
        proposal_ref=str(payload["proposal_ref"]), target=target, snapshot=snapshot, latest_evaluation=latest,
        current_graph=current_graph, rollback_graph=base_graph, policy=policy, action=str(payload["action"]), reason_ref=str(payload["reason_ref"]),
        proposer_ref=grant.subject_ref, proposed_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_proposal(value), required_role=ROLE_REMEDIATION_PROPOSER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT proposal_json FROM remediation_proposal WHERE proposal_ref=?", (value.proposal_ref,)).fetchone()
    if row is not None:
        current = proposal_from_dict(json.loads(row[0]))
        if current == value: return current
        raise ValueError("remediation proposal_ref is immutable")
    conn.execute("INSERT INTO remediation_proposal(proposal_hash,proposal_ref,snapshot_hash,target_hash,action,proposal_json) VALUES(?,?,?,?,?,?)", (value.proposal_hash,value.proposal_ref,value.snapshot_hash,value.target_hash,value.action,json.dumps(proposal_to_dict(value),sort_keys=True,separators=(",",":"))))
    return value


def _assess(conn, payload, *, grant, proof, enforcement):
    proposal = _proposal(conn, str(payload["proposal_hash"])); snapshot = _fresh_snapshot(conn, proposal.snapshot_hash); target = _target(conn, snapshot.target_hash); policy = _policy(conn, target.subject_identity_ref)
    latest = _latest_evaluation(conn, snapshot)
    value = assess_remediation_proposal(proposal=proposal, latest_evaluation=latest, policy=policy, assessor_ref=grant.subject_ref, assessed_at=enforcement.now)
    _enforce(grant, proof, action=action_assessment(value), required_role=ROLE_REMEDIATION_ASSESSOR, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT assessment_json FROM remediation_assessment WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    if row is not None:
        current = assessment_from_dict(json.loads(row[0]))
        if current == value: return current
        raise ValueError("remediation proposal assessment is immutable")
    conn.execute("INSERT INTO remediation_assessment(assessment_hash,proposal_hash,snapshot_hash,assessment_json) VALUES(?,?,?,?)", (value.assessment_hash,proposal.proposal_hash,proposal.snapshot_hash,json.dumps(assessment_to_dict(value),sort_keys=True,separators=(",",":"))))
    return value


def _select(conn, payload, *, grant, proof, enforcement):
    snapshot = _fresh_snapshot(conn, str(payload["snapshot_hash"])); target = _target(conn, snapshot.target_hash)
    proposals = _proposal_set(conn, snapshot.snapshot_hash)
    if not proposals: raise ValueError("no remediation proposals exist for snapshot")
    assessments = _assessment_set(conn, proposals)
    value = select_remediation(
        selection_ref=str(payload["selection_ref"]), snapshot=snapshot, proposals=proposals, assessments=assessments,
        selected_proposal_hash=str(payload["selected_proposal_hash"]), selector_ref=grant.subject_ref, selected_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_selection(value), required_role=ROLE_REMEDIATION_SELECTOR, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT selection_json FROM remediation_selection WHERE snapshot_hash=?", (snapshot.snapshot_hash,)).fetchone()
    if row is not None:
        current = selection_from_dict(json.loads(row[0]))
        if current == value: return current
        raise ValueError("remediation snapshot already has an immutable selection")
    conn.execute("INSERT INTO remediation_selection(selection_hash,selection_ref,snapshot_hash,selection_json) VALUES(?,?,?,?)", (value.selection_hash,value.selection_ref,value.snapshot_hash,json.dumps(selection_to_dict(value),sort_keys=True,separators=(",",":"))))
    return value


def _record_review(conn, payload, *, grant, proof, enforcement):
    selection = _selection(conn, str(payload["selection_hash"])); selection, snapshot = _fresh_selection(conn, selection); target = _target(conn, snapshot.target_hash)
    value = review_remediation_selection(selection=selection, decision=str(payload["decision"]), rationale_ref=str(payload["rationale_ref"]), reviewer_ref=grant.subject_ref, reviewed_at=enforcement.now)
    _enforce(grant, proof, action=action_review(value), required_role=ROLE_REMEDIATION_REVIEWER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT review_json FROM remediation_review WHERE selection_hash=?", (selection.selection_hash,)).fetchone()
    if row is not None:
        current = review_from_dict(json.loads(row[0]))
        if current == value: return current
        raise ValueError("remediation selection review is immutable")
    conn.execute("INSERT INTO remediation_review(review_hash,selection_hash,review_json) VALUES(?,?,?)", (value.review_hash,selection.selection_hash,json.dumps(review_to_dict(value),sort_keys=True,separators=(",",":"))))
    return value


def _apply(conn, payload, *, grant, proof, enforcement):
    selection = _selection(conn, str(payload["selection_hash"])); selection, snapshot = _fresh_selection(conn, selection); review = _review(conn, selection.selection_hash)
    target = _target(conn, snapshot.target_hash); proposal = _proposal(conn, selection.selected_proposal_hash); assessment = _assessment(conn, proposal.proposal_hash)
    base_graph, confirmed_graph, _, _, _, _, _ = _confirmed_bundle(conn, target.confirmed_revision_hash)
    current_graph = _graph(conn, target.subject_identity_ref)
    if current_graph.graph_hash != confirmed_graph.graph_hash:
        raise ValueError("remediation apply target graph is stale")
    new_graph, value = execute_remediation(
        target=target, snapshot=snapshot, current_graph=current_graph, rollback_graph=base_graph, proposal=proposal, assessment=assessment,
        selection=selection, review=review, applier_ref=grant.subject_ref, applied_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_apply(value), required_role=ROLE_REMEDIATION_APPLIER, required_scope=verification_scope(target.subject_identity_ref), enforcement=enforcement)
    row = conn.execute("SELECT execution_json FROM remediation_execution WHERE snapshot_hash=?", (snapshot.snapshot_hash,)).fetchone()
    if row is not None:
        current = json.loads(row[0])
        if current.get("execution_hash") == value.execution_hash: return new_graph, value
        raise ValueError("remediation snapshot already has an execution")
    if new_graph.graph_hash != current_graph.graph_hash:
        conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?", (json.dumps(graph_to_dict(new_graph),sort_keys=True,separators=(",",":")),target.subject_identity_ref))
    conn.execute("""INSERT INTO remediation_execution(execution_hash,snapshot_hash,selection_hash,action,old_graph_hash,new_graph_hash,old_graph_json,new_graph_json,proposal_json,assessment_json,selection_json,review_json,execution_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        value.execution_hash,snapshot.snapshot_hash,selection.selection_hash,value.action,current_graph.graph_hash,new_graph.graph_hash,
        json.dumps(graph_to_dict(current_graph),sort_keys=True,separators=(",",":")),json.dumps(graph_to_dict(new_graph),sort_keys=True,separators=(",",":")),
        json.dumps(proposal_to_dict(proposal),sort_keys=True,separators=(",",":")),json.dumps(assessment_to_dict(assessment),sort_keys=True,separators=(",",":")),
        json.dumps(selection_to_dict(selection),sort_keys=True,separators=(",",":")),json.dumps(review_to_dict(review),sort_keys=True,separators=(",",":")),
        json.dumps(execution_to_dict(value),sort_keys=True,separators=(",",":")),
    ))
    return new_graph, value


def _state(conn: sqlite3.Connection) -> dict[str, object]:
    policies = conn.execute("SELECT policy_json FROM remediation_policy ORDER BY subject_identity_ref").fetchall()
    proposals = conn.execute("SELECT proposal_json FROM remediation_proposal ORDER BY proposal_hash").fetchall()
    assessments = conn.execute("SELECT assessment_json FROM remediation_assessment ORDER BY assessment_hash").fetchall()
    selections = conn.execute("SELECT selection_json FROM remediation_selection ORDER BY selection_hash").fetchall()
    reviews = conn.execute("SELECT review_json FROM remediation_review ORDER BY review_hash").fetchall()
    executions = conn.execute("SELECT execution_json FROM remediation_execution ORDER BY execution_hash").fetchall()
    return {
        "policies":[policy_to_dict(policy_from_dict(json.loads(row[0]))) for row in policies],
        "proposals":[proposal_to_dict(proposal_from_dict(json.loads(row[0]))) for row in proposals],
        "assessments":[assessment_to_dict(assessment_from_dict(json.loads(row[0]))) for row in assessments],
        "selections":[selection_to_dict(selection_from_dict(json.loads(row[0]))) for row in selections],
        "reviews":[review_to_dict(review_from_dict(json.loads(row[0]))) for row in reviews],
        "executions":[json.loads(row[0]) for row in executions],
    }


def execute_remediation_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != REMEDIATION_PROTOCOL: raise ValueError("unsupported remediation protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id: raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in REMEDIATION_OPERATIONS: raise ValueError("unsupported remediation operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_remediation_state": return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,**_state(conn)}
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant")); proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_remediation_policy":
            value=_register_policy(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT"); return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,"policy":policy_to_dict(value)}
        if operation == "register_remediation_proposal":
            value=_register_proposal(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT"); return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,"proposal":proposal_to_dict(value)}
        if operation == "assess_remediation_proposal":
            value=_assess(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT"); return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,"assessment":assessment_to_dict(value)}
        if operation == "select_remediation":
            value=_select(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT"); return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,"selection":selection_to_dict(value)}
        if operation == "record_remediation_review":
            value=_record_review(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT"); return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,"review":review_to_dict(value)}
        graph,value=_apply(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
        return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"ok":True,"graph":graph_to_dict(graph),"execution":execution_to_dict(value)}
    except Exception:
        if conn.in_transaction: conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
