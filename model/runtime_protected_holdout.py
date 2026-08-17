from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.protected_holdout import (
    EvaluationExposureLineageReceipt,
    FinalConfirmationCase,
    FinalConfirmationReceipt,
    FinalConfirmedGraphRevisionReceipt,
    ProtectedFinalHoldoutPolicy,
    ProtectedFinalHoldoutSeal,
    apply_final_confirmed_selection,
    confirm_on_protected_holdout,
    make_protected_final_holdout_policy,
    make_protected_final_holdout_seal,
)
from model.runtime_calibration import pair_from_dict, pair_to_dict
from model.runtime_dependency_graph import _graph, graph_to_dict
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_search_budget import (
    _candidate,
    _connect as search_connect,
    _current_search_state,
    _evaluation_bundle,
    _reservation,
    _review,
    _selection,
    evaluation_to_dict,
    reservation_to_dict,
    review_to_dict,
    selection_to_dict,
)
from model.runtime_structural_validation import candidate_to_dict, validation_to_dict
from model.runtime_verification import verification_scope
from model.search_budget import select_search_budget_candidate

FINAL_PROTOCOL = "ATMAN-FINAL/1.17"
FINAL_OPERATIONS = {
    "register_final_holdout_policy",
    "seal_final_holdout_pool",
    "confirm_selected_structure",
    "apply_final_confirmed_selection",
    "get_final_holdout_state",
}

ROLE_FINAL_POLICY_KEEPER = "FINAL_HOLDOUT_POLICY_KEEPER"
ROLE_FINAL_POOL_KEEPER = "FINAL_HOLDOUT_POOL_KEEPER"
ROLE_FINAL_CONFIRMER = "FINAL_HOLDOUT_CONFIRMER"
ROLE_FINAL_APPLIER = "FINAL_CONFIRMED_STRUCTURAL_APPLIER"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def policy_to_dict(value: ProtectedFinalHoldoutPolicy) -> dict[str, object]:
    value.validate(); return asdict(value)


def policy_from_dict(data: Mapping[str, object]) -> ProtectedFinalHoldoutPolicy:
    result = ProtectedFinalHoldoutPolicy(
        policy_ref=str(data["policy_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        min_final_samples=int(data["min_final_samples"]),
        min_final_regularized_improvement_ppm=int(data["min_final_regularized_improvement_ppm"]),
        registered_at=int(data["registered_at"]),
        policy_hash=str(data["policy_hash"]),
    )
    result.validate(); return result


def pool_to_dict(value: ProtectedFinalHoldoutSeal) -> dict[str, object]:
    value.validate(); return asdict(value)


def pool_from_dict(data: Mapping[str, object]) -> ProtectedFinalHoldoutSeal:
    result = ProtectedFinalHoldoutSeal(
        pool_ref=str(data["pool_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        pair_key=str(data["pair_key"]),
        policy_hash=str(data["policy_hash"]),
        generation=int(data["generation"]),
        sample_count=int(data["sample_count"]),
        sample_commitment=str(data["sample_commitment"]),
        previous_pool_hash=None if data.get("previous_pool_hash") is None else str(data["previous_pool_hash"]),
        keeper_ref=str(data["keeper_ref"]),
        sealed_at=int(data["sealed_at"]),
        pool_hash=str(data["pool_hash"]),
    )
    result.validate(); return result


def case_to_dict(value: FinalConfirmationCase) -> dict[str, object]:
    value.validate(); return asdict(value)


def case_from_dict(data: Mapping[str, object]) -> FinalConfirmationCase:
    result = FinalConfirmationCase(
        sample_hash=str(data["sample_hash"]),
        parent_positive=bool(data["parent_positive"]),
        child_positive=bool(data["child_positive"]),
        base_predicted_positive_bps=int(data["base_predicted_positive_bps"]),
        proposed_predicted_positive_bps=int(data["proposed_predicted_positive_bps"]),
        base_brier_score_ppm=int(data["base_brier_score_ppm"]),
        proposed_brier_score_ppm=int(data["proposed_brier_score_ppm"]),
        case_hash=str(data["case_hash"]),
    )
    result.validate(); return result


def lineage_to_dict(value: EvaluationExposureLineageReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["discovery_sample_hashes"] = list(value.discovery_sample_hashes)
    data["validation_sample_hashes"] = list(value.validation_sample_hashes)
    data["search_family_reservation_hashes"] = list(value.search_family_reservation_hashes)
    data["final_case_hashes"] = list(value.final_case_hashes)
    return data


def lineage_from_dict(data: Mapping[str, object]) -> EvaluationExposureLineageReceipt:
    result = EvaluationExposureLineageReceipt(
        candidate_hash=str(data["candidate_hash"]),
        discovery_sample_hashes=tuple(str(v) for v in data.get("discovery_sample_hashes", [])),
        validation_sample_hashes=tuple(str(v) for v in data.get("validation_sample_hashes", [])),
        search_reservation_hash=str(data["search_reservation_hash"]),
        search_evaluation_hash=str(data["search_evaluation_hash"]),
        search_selection_hash=str(data["search_selection_hash"]),
        search_family_reservation_hashes=tuple(str(v) for v in data.get("search_family_reservation_hashes", [])),
        final_pool_hash=str(data["final_pool_hash"]),
        final_case_hashes=tuple(str(v) for v in data.get("final_case_hashes", [])),
        lineage_hash=str(data["lineage_hash"]),
    )
    result.validate(); return result


def confirmation_to_dict(value: FinalConfirmationReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def confirmation_from_dict(data: Mapping[str, object]) -> FinalConfirmationReceipt:
    result = FinalConfirmationReceipt(
        selection_hash=str(data["selection_hash"]),
        review_hash=str(data["review_hash"]),
        candidate_hash=str(data["candidate_hash"]),
        search_evaluation_hash=str(data["search_evaluation_hash"]),
        pool_hash=str(data["pool_hash"]),
        pool_generation=int(data["pool_generation"]),
        lineage_hash=str(data["lineage_hash"]),
        evaluated_case_count=int(data["evaluated_case_count"]),
        min_final_samples=int(data["min_final_samples"]),
        base_mean_brier_ppm=None if data.get("base_mean_brier_ppm") is None else int(data["base_mean_brier_ppm"]),
        proposed_mean_brier_ppm=None if data.get("proposed_mean_brier_ppm") is None else int(data["proposed_mean_brier_ppm"]),
        base_edge_count=int(data["base_edge_count"]),
        proposed_edge_count=int(data["proposed_edge_count"]),
        edge_penalty_ppm=int(data["edge_penalty_ppm"]),
        base_regularized_brier_ppm=None if data.get("base_regularized_brier_ppm") is None else int(data["base_regularized_brier_ppm"]),
        proposed_regularized_brier_ppm=None if data.get("proposed_regularized_brier_ppm") is None else int(data["proposed_regularized_brier_ppm"]),
        regularized_improvement_ppm=None if data.get("regularized_improvement_ppm") is None else int(data["regularized_improvement_ppm"]),
        min_final_regularized_improvement_ppm=int(data["min_final_regularized_improvement_ppm"]),
        status=str(data["status"]),
        pool_keeper_ref=str(data["pool_keeper_ref"]),
        confirmer_ref=str(data["confirmer_ref"]),
        confirmed_at=int(data["confirmed_at"]),
        confirmation_hash=str(data["confirmation_hash"]),
    )
    result.validate(); return result


def revision_to_dict(value: FinalConfirmedGraphRevisionReceipt) -> dict[str, object]:
    value.validate(); return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = search_connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protected_final_holdout_policy (
            subject_identity_ref TEXT PRIMARY KEY,
            policy_ref TEXT NOT NULL UNIQUE,
            policy_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protected_final_holdout_pool (
            pool_hash TEXT PRIMARY KEY,
            pool_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            generation INTEGER NOT NULL,
            seal_json TEXT NOT NULL,
            samples_json TEXT NOT NULL,
            consumed_by_selection_hash TEXT,
            UNIQUE(subject_identity_ref,pair_key,generation)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protected_final_sample_registry (
            sample_hash TEXT PRIMARY KEY,
            pool_hash TEXT NOT NULL,
            subject_identity_ref TEXT NOT NULL,
            pair_key TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS final_confirmation_receipt (
            confirmation_hash TEXT PRIMARY KEY,
            pool_hash TEXT NOT NULL UNIQUE,
            selection_hash TEXT NOT NULL UNIQUE,
            lineage_json TEXT NOT NULL,
            confirmation_json TEXT NOT NULL,
            cases_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS final_confirmed_revision_history (
            revision_hash TEXT PRIMARY KEY,
            selection_hash TEXT NOT NULL UNIQUE,
            confirmation_hash TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            base_graph_hash TEXT NOT NULL,
            new_graph_hash TEXT NOT NULL,
            base_graph_json TEXT NOT NULL,
            new_graph_json TEXT NOT NULL,
            pool_json TEXT NOT NULL,
            candidate_json TEXT NOT NULL,
            underlying_validation_json TEXT NOT NULL,
            search_evaluation_json TEXT NOT NULL,
            selection_json TEXT NOT NULL,
            review_json TEXT NOT NULL,
            lineage_json TEXT NOT NULL,
            confirmation_json TEXT NOT NULL,
            revision_json TEXT NOT NULL
        )
    """)
    return conn


def _enforce(grant: AuthorityGrant, proof: AuthorityProof, *, action: object, required_role: str, required_scope: str, enforcement: EnforcementContext) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(
        grant, proof, action=action,
        trusted_issuer_keys=enforcement.trusted_issuer_keys,
        current_policy_generation=enforcement.policy_generation,
        now=enforcement.now,
    )
    failures = list(limitations)
    if proof.role != required_role: failures.append("required_role_mismatch")
    if proof.scope != required_scope: failures.append("required_scope_mismatch")
    if not valid or failures:
        raise PermissionError("protected final holdout authority failed: " + ",".join(dict.fromkeys(failures)))


def _policy(conn: sqlite3.Connection, subject: str) -> ProtectedFinalHoldoutPolicy:
    row = conn.execute("SELECT policy_json FROM protected_final_holdout_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is None: raise ValueError("protected final holdout policy is not registered")
    return policy_from_dict(json.loads(row[0]))


def _pool(conn: sqlite3.Connection, pool_hash: str):
    row = conn.execute("SELECT seal_json,samples_json,consumed_by_selection_hash FROM protected_final_holdout_pool WHERE pool_hash=?", (pool_hash,)).fetchone()
    if row is None: raise ValueError("unknown protected final holdout pool")
    seal = pool_from_dict(json.loads(row[0]))
    samples = tuple(pair_from_dict(item) for item in json.loads(row[1]))
    return seal, samples, None if row[2] is None else str(row[2])


def _confirmation(conn: sqlite3.Connection, selection_hash: str):
    row = conn.execute("SELECT lineage_json,confirmation_json,cases_json FROM final_confirmation_receipt WHERE selection_hash=?", (selection_hash,)).fetchone()
    if row is None: raise ValueError("final confirmation is not recorded")
    lineage = lineage_from_dict(json.loads(row[0]))
    confirmation = confirmation_from_dict(json.loads(row[1]))
    cases = tuple(case_from_dict(item) for item in json.loads(row[2]))
    return cases, lineage, confirmation


def action_register_policy(value: ProtectedFinalHoldoutPolicy) -> dict[str, object]:
    value.validate(); return {"operation":"register_final_holdout_policy","subject_identity_ref":value.subject_identity_ref,"policy_hash":value.policy_hash,"min_final_samples":value.min_final_samples,"min_final_regularized_improvement_ppm":value.min_final_regularized_improvement_ppm}


def action_seal_pool(value: ProtectedFinalHoldoutSeal) -> dict[str, object]:
    value.validate(); return {"operation":"seal_final_holdout_pool","pool_hash":value.pool_hash,"subject_identity_ref":value.subject_identity_ref,"pair_key":value.pair_key,"generation":value.generation,"sample_count":value.sample_count,"sample_commitment":value.sample_commitment}


def action_confirm_request(selection_hash: str, pool_hash: str) -> dict[str, object]:
    return {"operation":"confirm_selected_structure","selection_hash":selection_hash,"pool_hash":pool_hash}


def action_apply(value: FinalConfirmedGraphRevisionReceipt) -> dict[str, object]:
    value.validate(); return {"operation":"apply_final_confirmed_selection","selection_hash":value.selection_hash,"confirmation_hash":value.confirmation_hash,"base_graph_hash":value.base_graph_hash,"new_graph_hash":value.new_graph_hash,"revision_hash":value.revision_hash}


def _register_policy(conn, payload, *, grant, proof, enforcement):
    subject = str(payload["subject_identity_ref"])
    policy = make_protected_final_holdout_policy(
        policy_ref=str(payload["policy_ref"]), subject_identity_ref=subject,
        min_final_samples=int(payload.get("min_final_samples",4)),
        min_final_regularized_improvement_ppm=int(payload.get("min_final_regularized_improvement_ppm",0)),
        registered_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_register_policy(policy), required_role=ROLE_FINAL_POLICY_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    row = conn.execute("SELECT policy_json FROM protected_final_holdout_policy WHERE subject_identity_ref=?", (subject,)).fetchone()
    if row is not None:
        current = policy_from_dict(json.loads(row[0]))
        if current == policy: return current
        raise ValueError("protected final holdout policy is immutable once registered")
    conn.execute("INSERT INTO protected_final_holdout_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (subject,policy.policy_ref,json.dumps(policy_to_dict(policy),sort_keys=True,separators=(",",":"))))
    return policy


def _seal(conn, payload, *, grant, proof, enforcement):
    subject = str(payload["subject_identity_ref"])
    policy = _policy(conn, subject)
    raw_samples = payload.get("samples", [])
    if not isinstance(raw_samples, list) or not raw_samples:
        raise ValueError("protected final holdout samples are required")
    samples = tuple(pair_from_dict(_mapping(item,"protected_sample")) for item in raw_samples)
    pair_key = samples[0].pair_key
    if any(sample.pair_key != pair_key for sample in samples):
        raise ValueError("protected final holdout samples must share one pair key")
    for sample in samples:
        if conn.execute("SELECT 1 FROM calibration_dependency_pair WHERE sample_hash=?", (sample.sample_hash,)).fetchone() is not None:
            raise ValueError("new split is not fresh evidence: protected sample already appeared in discovery/validation history")
        if conn.execute("SELECT 1 FROM protected_final_sample_registry WHERE sample_hash=?", (sample.sample_hash,)).fetchone() is not None:
            raise ValueError("protected holdout rotation requires genuinely new sample hashes")
    previous_row = conn.execute("SELECT seal_json,consumed_by_selection_hash FROM protected_final_holdout_pool WHERE subject_identity_ref=? AND pair_key=? ORDER BY generation DESC LIMIT 1", (subject,pair_key)).fetchone()
    if previous_row is None:
        previous = None; generation = 0
    else:
        previous = pool_from_dict(json.loads(previous_row[0])); generation = previous.generation + 1
        if previous_row[1] is None:
            raise ValueError("cannot rotate protected final holdout before previous pool is consumed")
    seal = make_protected_final_holdout_seal(
        pool_ref=str(payload["pool_ref"]), subject_identity_ref=subject, samples=samples, policy=policy,
        generation=generation, previous_pool=previous, keeper_ref=grant.subject_ref, sealed_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_seal_pool(seal), required_role=ROLE_FINAL_POOL_KEEPER, required_scope=verification_scope(subject), enforcement=enforcement)
    conn.execute("INSERT INTO protected_final_holdout_pool(pool_hash,pool_ref,subject_identity_ref,pair_key,generation,seal_json,samples_json,consumed_by_selection_hash) VALUES(?,?,?,?,?,?,?,NULL)", (seal.pool_hash,seal.pool_ref,subject,pair_key,generation,json.dumps(pool_to_dict(seal),sort_keys=True,separators=(",",":")),json.dumps([pair_to_dict(item) for item in samples],sort_keys=True,separators=(",",":"))))
    for sample in samples:
        conn.execute("INSERT INTO protected_final_sample_registry(sample_hash,pool_hash,subject_identity_ref,pair_key) VALUES(?,?,?,?)", (sample.sample_hash,seal.pool_hash,subject,pair_key))
    return seal


def _fresh_search_chain(conn, selection_hash: str):
    selection = _selection(conn, selection_hash)
    review = _review(conn, selection.selection_hash)
    if selection.status != "SELECTED" or selection.selected_candidate_hash is None:
        raise ValueError("final confirmation requires a selected search-budget candidate")
    structural, search_policy, current_graph, samples, reservations, candidates, evaluations = _current_search_state(conn, subject=selection.subject_identity_ref, pair_key=selection.pair_key)
    fresh = select_search_budget_candidate(selection_ref=selection.selection_ref,current_candidates=candidates,current_evaluations=evaluations,all_family_reservations=reservations,search_policy=search_policy,selector_ref=selection.selector_ref,selected_at=selection.selected_at)
    if fresh != selection:
        raise ValueError("stale final confirmation state: search exposure or candidate state changed after selection")
    candidate = _candidate(conn, selection.selected_candidate_hash)
    reservation = _reservation(conn, candidate.candidate_hash)
    underlying, evaluation = _evaluation_bundle(conn, candidate.candidate_hash)
    return selection, review, structural, current_graph, samples, candidate, reservation, underlying, evaluation, reservations, candidates, evaluations, search_policy


def _assert_pool_not_leaked(conn, protected_samples):
    for sample in protected_samples:
        if conn.execute("SELECT 1 FROM calibration_dependency_pair WHERE sample_hash=?", (sample.sample_hash,)).fetchone() is not None:
            raise ValueError("protected final holdout leaked into discovery/validation history")


def _confirm(conn, payload, *, grant, proof, enforcement):
    selection_hash = str(payload["selection_hash"]); pool_hash = str(payload["pool_hash"])
    selection = _selection(conn, selection_hash)
    seal, protected_samples, consumed_by = _pool(conn, pool_hash)
    _enforce(grant, proof, action=action_confirm_request(selection_hash,pool_hash), required_role=ROLE_FINAL_CONFIRMER, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    existing = conn.execute("SELECT lineage_json,confirmation_json,cases_json FROM final_confirmation_receipt WHERE pool_hash=?", (pool_hash,)).fetchone()
    if existing is not None:
        lineage = lineage_from_dict(json.loads(existing[0])); confirmation = confirmation_from_dict(json.loads(existing[1])); cases = tuple(case_from_dict(item) for item in json.loads(existing[2]))
        if confirmation.selection_hash != selection_hash or confirmation.confirmer_ref != grant.subject_ref:
            raise ValueError("protected final holdout pool is already consumed by another confirmation")
        return cases, lineage, confirmation
    if consumed_by is not None:
        raise ValueError("protected final holdout pool is already consumed")
    chain = _fresh_search_chain(conn, selection_hash)
    selection, review, structural, current_graph, samples, candidate, reservation, underlying, evaluation = chain[:9]
    if seal.subject_identity_ref != selection.subject_identity_ref or seal.pair_key != selection.pair_key:
        raise ValueError("protected final holdout pool does not match selected search context")
    _assert_pool_not_leaked(conn, protected_samples)
    final_policy = _policy(conn, selection.subject_identity_ref)
    cases, lineage, confirmation = confirm_on_protected_holdout(
        candidate=candidate,reservation=reservation,search_evaluation=evaluation,selection=selection,review=review,
        base_graph=current_graph,exposed_samples=tuple(samples),protected_samples=protected_samples,
        structural_policy=structural,final_policy=final_policy,pool=seal,confirmer_ref=grant.subject_ref,confirmed_at=enforcement.now,
    )
    conn.execute("UPDATE protected_final_holdout_pool SET consumed_by_selection_hash=? WHERE pool_hash=? AND consumed_by_selection_hash IS NULL", (selection_hash,pool_hash))
    if conn.total_changes < 1:
        raise ValueError("protected final holdout pool consumption race")
    conn.execute("INSERT INTO final_confirmation_receipt(confirmation_hash,pool_hash,selection_hash,lineage_json,confirmation_json,cases_json) VALUES(?,?,?,?,?,?)", (confirmation.confirmation_hash,pool_hash,selection_hash,json.dumps(lineage_to_dict(lineage),sort_keys=True,separators=(",",":")),json.dumps(confirmation_to_dict(confirmation),sort_keys=True,separators=(",",":")),json.dumps([case_to_dict(item) for item in cases],sort_keys=True,separators=(",",":"))))
    return cases, lineage, confirmation


def _apply(conn, payload, *, grant, proof, enforcement):
    selection_hash = str(payload["selection_hash"])
    cases, lineage, confirmation = _confirmation(conn, selection_hash)
    if confirmation.status != "FINAL_CONFIRMED":
        raise ValueError("final apply requires FINAL_CONFIRMED outcome")
    chain = _fresh_search_chain(conn, selection_hash)
    selection, review, structural, current_graph, samples, candidate, reservation, underlying, evaluation = chain[:9]
    seal, protected_samples, consumed_by = _pool(conn, confirmation.pool_hash)
    if consumed_by != selection_hash:
        raise ValueError("final confirmation pool consumption binding mismatch")
    _assert_pool_not_leaked(conn, protected_samples)
    if confirmation.pool_hash != seal.pool_hash or confirmation.candidate_hash != candidate.candidate_hash or confirmation.search_evaluation_hash != evaluation.evaluation_hash:
        raise ValueError("stale final confirmation chain")
    new_graph, revision = apply_final_confirmed_selection(
        current_graph=current_graph,candidate=candidate,reservation=reservation,underlying_validation=underlying,
        search_evaluation=evaluation,selection=selection,review=review,confirmation=confirmation,
        applier_ref=grant.subject_ref,applied_at=enforcement.now,
    )
    _enforce(grant, proof, action=action_apply(revision), required_role=ROLE_FINAL_APPLIER, required_scope=verification_scope(selection.subject_identity_ref), enforcement=enforcement)
    if conn.execute("SELECT 1 FROM final_confirmed_revision_history WHERE selection_hash=?", (selection_hash,)).fetchone() is not None:
        raise ValueError("final-confirmed selection has already been applied")
    base_json=json.dumps(graph_to_dict(current_graph),sort_keys=True,separators=(",",":")); new_json=json.dumps(graph_to_dict(new_graph),sort_keys=True,separators=(",",":"))
    conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?", (new_json,selection.subject_identity_ref))
    conn.execute("INSERT INTO final_confirmed_revision_history(revision_hash,selection_hash,confirmation_hash,subject_identity_ref,base_graph_hash,new_graph_hash,base_graph_json,new_graph_json,pool_json,candidate_json,underlying_validation_json,search_evaluation_json,selection_json,review_json,lineage_json,confirmation_json,revision_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        revision.revision_hash,selection_hash,confirmation.confirmation_hash,selection.subject_identity_ref,current_graph.graph_hash,new_graph.graph_hash,base_json,new_json,
        json.dumps(pool_to_dict(seal),sort_keys=True,separators=(",",":")),json.dumps(candidate_to_dict(candidate),sort_keys=True,separators=(",",":")),json.dumps(validation_to_dict(underlying),sort_keys=True,separators=(",",":")),json.dumps(evaluation_to_dict(evaluation),sort_keys=True,separators=(",",":")),json.dumps(selection_to_dict(selection),sort_keys=True,separators=(",",":")),json.dumps(review_to_dict(review),sort_keys=True,separators=(",",":")),json.dumps(lineage_to_dict(lineage),sort_keys=True,separators=(",",":")),json.dumps(confirmation_to_dict(confirmation),sort_keys=True,separators=(",",":")),json.dumps(revision_to_dict(revision),sort_keys=True,separators=(",",":")),
    ))
    return new_graph, revision


def _state(conn):
    policies=conn.execute("SELECT policy_json FROM protected_final_holdout_policy ORDER BY subject_identity_ref").fetchall()
    pools=conn.execute("SELECT seal_json,consumed_by_selection_hash FROM protected_final_holdout_pool ORDER BY subject_identity_ref,pair_key,generation").fetchall()
    confirmations=conn.execute("SELECT confirmation_hash FROM final_confirmation_receipt ORDER BY confirmation_hash").fetchall()
    revisions=conn.execute("SELECT revision_hash FROM final_confirmed_revision_history ORDER BY revision_hash").fetchall()
    return {
        "policies":[policy_to_dict(policy_from_dict(json.loads(row[0]))) for row in policies],
        "pools":[{"seal":pool_to_dict(pool_from_dict(json.loads(row[0]))),"consumed":row[1] is not None} for row in pools],
        "confirmation_hashes":[str(row[0]) for row in confirmations],
        "revision_hashes":[str(row[0]) for row in revisions],
    }


def execute_protected_holdout_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != FINAL_PROTOCOL: raise ValueError("unsupported protected final holdout protocol")
    request_id=str(request.get("request_id",""))
    if not request_id: raise ValueError("request_id is required")
    operation=str(request.get("operation",""))
    if operation not in FINAL_OPERATIONS: raise ValueError("unsupported protected final holdout operation")
    payload=_mapping(request.get("payload",{}),"payload")
    conn=_connect(db_path)
    try:
        if operation=="get_final_holdout_state":
            return {"protocol":FINAL_PROTOCOL,"request_id":request_id,"ok":True,**_state(conn)}
        grant=authority_grant_from_dict(_mapping(request.get("grant"),"grant")); proof=authority_proof_from_dict(_mapping(request.get("proof"),"proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation=="register_final_holdout_policy":
            value=_register_policy(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":FINAL_PROTOCOL,"request_id":request_id,"ok":True,"policy":policy_to_dict(value)}
        if operation=="seal_final_holdout_pool":
            value=_seal(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":FINAL_PROTOCOL,"request_id":request_id,"ok":True,"pool":pool_to_dict(value)}
        if operation=="confirm_selected_structure":
            cases,lineage,confirmation=_confirm(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
            return {"protocol":FINAL_PROTOCOL,"request_id":request_id,"ok":True,"lineage":lineage_to_dict(lineage),"confirmation":confirmation_to_dict(confirmation),"cases":[case_to_dict(item) for item in cases]}
        graph,revision=_apply(conn,payload,grant=grant,proof=proof,enforcement=enforcement); conn.execute("COMMIT")
        return {"protocol":FINAL_PROTOCOL,"request_id":request_id,"ok":True,"graph":graph_to_dict(graph),"revision":revision_to_dict(revision)}
    except Exception:
        if conn.in_transaction: conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
