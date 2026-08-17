from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.multihypothesis import (
    DuplicateEvidenceReceipt,
    EvidenceDependencyDeclaration,
    HypothesisDistribution,
    MultiEvidenceReceipt,
    MultiEvidenceRule,
    MultiHypothesisUpdateReceipt,
    MultiLikelihoodModel,
    build_duplicate_evidence_receipt,
    build_multi_hypothesis_update,
    interpret_multi_completion,
    make_evidence_dependency,
    make_hypothesis_distribution,
    make_multi_evidence_rule,
    make_multi_likelihood_model,
    multi_expected_information_gain,
)
from model.multihypothesis_rebase import MultiLikelihoodRebaseReceipt, rebase_multi_likelihood_model
from model.runtime_bayesian import _candidate_by_hash, _completion, _connect as bayes_connect
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import verification_scope

MULTI_PROTOCOL = "ATMAN-MULTI/1.11"
MULTI_OPERATIONS = {
    "register_distribution",
    "register_multi_likelihood_model",
    "register_evidence_dependency",
    "register_multi_evidence_rule",
    "preview_multi_update",
    "apply_multi_update",
    "get_multi_state",
}

ROLE_MULTI_MODEL_KEEPER = "MULTI_HYPOTHESIS_MODEL_KEEPER"
ROLE_DEPENDENCY_KEEPER = "EVIDENCE_DEPENDENCY_KEEPER"
ROLE_MULTI_RULE_KEEPER = "MULTI_EVIDENCE_RULE_KEEPER"
ROLE_MULTI_UPDATE_KEEPER = "MULTI_HYPOTHESIS_UPDATE_KEEPER"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def distribution_to_dict(value: HypothesisDistribution) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["probability_bps"] = [[key, probability] for key, probability in value.probability_bps]
    return data


def distribution_from_dict(data: Mapping[str, object]) -> HypothesisDistribution:
    result = HypothesisDistribution(
        distribution_ref=str(data["distribution_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        probability_bps=tuple((str(item[0]), int(item[1])) for item in data["probability_bps"]),
        evidence_state_hash=str(data["evidence_state_hash"]),
        generation=int(data["generation"]),
        distribution_hash=str(data["distribution_hash"]),
    )
    result.validate()
    return result


def model_to_dict(value: MultiLikelihoodModel) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["positive_likelihood_bps"] = [[key, probability] for key, probability in value.positive_likelihood_bps]
    data["conditioning_evidence_hashes"] = list(value.conditioning_evidence_hashes)
    return data


def model_from_dict(data: Mapping[str, object]) -> MultiLikelihoodModel:
    result = MultiLikelihoodModel(
        candidate_hash=str(data["candidate_hash"]),
        distribution_hash=str(data["distribution_hash"]),
        positive_likelihood_bps=tuple((str(item[0]), int(item[1])) for item in data["positive_likelihood_bps"]),
        conditioning_evidence_hashes=tuple(str(value) for value in data.get("conditioning_evidence_hashes", [])),
        model_ref=str(data["model_ref"]),
        model_generation=int(data["model_generation"]),
        model_hash=str(data["model_hash"]),
    )
    result.validate()
    return result


def dependency_to_dict(value: EvidenceDependencyDeclaration) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["parent_evidence_hashes"] = list(value.parent_evidence_hashes)
    return data


def dependency_from_dict(data: Mapping[str, object]) -> EvidenceDependencyDeclaration:
    result = EvidenceDependencyDeclaration(
        candidate_hash=str(data["candidate_hash"]),
        source_event_hash=str(data["source_event_hash"]),
        derivation_hash=str(data["derivation_hash"]),
        dependency_group_ref=str(data["dependency_group_ref"]),
        mode=str(data["mode"]),
        parent_evidence_hashes=tuple(str(value) for value in data.get("parent_evidence_hashes", [])),
        declaration_ref=str(data["declaration_ref"]),
        declaration_generation=int(data["declaration_generation"]),
        declared_at=int(data["declared_at"]),
        dependency_hash=str(data["dependency_hash"]),
    )
    result.validate()
    return result


def rule_to_dict(value: MultiEvidenceRule) -> dict[str, object]:
    value.validate()
    return asdict(value)


def rule_from_dict(data: Mapping[str, object]) -> MultiEvidenceRule:
    result = MultiEvidenceRule(
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


def evidence_to_dict(value: MultiEvidenceReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["parent_evidence_hashes"] = list(value.parent_evidence_hashes)
    return data


def evidence_from_dict(data: Mapping[str, object]) -> MultiEvidenceReceipt:
    result = MultiEvidenceReceipt(
        candidate_hash=str(data["candidate_hash"]),
        work_hash=str(data["work_hash"]),
        completion_hash=str(data["completion_hash"]),
        completion_decision=str(data["completion_decision"]),
        prior_distribution_hash=str(data["prior_distribution_hash"]),
        likelihood_model_hash=str(data["likelihood_model_hash"]),
        dependency_hash=str(data["dependency_hash"]),
        rule_hash=str(data["rule_hash"]),
        source_event_hash=str(data["source_event_hash"]),
        derivation_hash=str(data["derivation_hash"]),
        dependency_group_ref=str(data["dependency_group_ref"]),
        dependency_mode=str(data["dependency_mode"]),
        parent_evidence_hashes=tuple(str(value) for value in data.get("parent_evidence_hashes", [])),
        outcome=str(data["outcome"]),
        interpreted_at=int(data["interpreted_at"]),
        evidence_hash=str(data["evidence_hash"]),
    )
    result.validate()
    return result


def update_to_dict(value: MultiHypothesisUpdateReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["prior_probability_bps"] = [[key, probability] for key, probability in value.prior_probability_bps]
    data["posterior_probability_bps"] = [[key, probability] for key, probability in value.posterior_probability_bps]
    return data


def duplicate_to_dict(value: DuplicateEvidenceReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def rebase_to_dict(value: MultiLikelihoodRebaseReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["conditioning_evidence_hashes"] = list(value.conditioning_evidence_hashes)
    return data


def _connect(db_path: str) -> sqlite3.Connection:
    conn = bayes_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_hypothesis_distribution (
            distribution_ref TEXT PRIMARY KEY,
            distribution_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_candidate_binding (
            candidate_hash TEXT PRIMARY KEY,
            distribution_ref TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_likelihood_model (
            candidate_hash TEXT PRIMARY KEY,
            model_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_evidence_dependency (
            candidate_hash TEXT PRIMARY KEY,
            dependency_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_evidence_rule (
            candidate_hash TEXT PRIMARY KEY,
            rule_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_evidence_history (
            evidence_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL,
            completion_hash TEXT NOT NULL UNIQUE,
            source_event_hash TEXT NOT NULL UNIQUE,
            dependency_group_ref TEXT NOT NULL,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_duplicate_history (
            duplicate_hash TEXT PRIMARY KEY,
            evidence_hash TEXT NOT NULL UNIQUE,
            completion_hash TEXT NOT NULL UNIQUE,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_update_history (
            update_hash TEXT PRIMARY KEY,
            candidate_hash TEXT NOT NULL,
            prior_distribution_hash TEXT NOT NULL UNIQUE,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS multi_likelihood_rebase_history (
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
        raise PermissionError("multi-hypothesis authority failed: " + ",".join(dict.fromkeys(failures)))


def _distribution(conn: sqlite3.Connection, distribution_ref: str) -> HypothesisDistribution:
    row = conn.execute(
        "SELECT distribution_json FROM multi_hypothesis_distribution WHERE distribution_ref=?",
        (distribution_ref,),
    ).fetchone()
    if row is None:
        raise ValueError("unknown multi-hypothesis distribution")
    return distribution_from_dict(json.loads(row[0]))


def _distribution_for_candidate(conn: sqlite3.Connection, candidate_hash: str) -> HypothesisDistribution:
    row = conn.execute(
        "SELECT distribution_ref FROM multi_candidate_binding WHERE candidate_hash=?",
        (candidate_hash,),
    ).fetchone()
    if row is None:
        raise ValueError("candidate is not bound to a multi-hypothesis distribution")
    return _distribution(conn, str(row[0]))


def _model(conn: sqlite3.Connection, candidate_hash: str) -> MultiLikelihoodModel:
    row = conn.execute("SELECT model_json FROM multi_likelihood_model WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("multi-hypothesis update requires likelihood model")
    return model_from_dict(json.loads(row[0]))


def _dependency(conn: sqlite3.Connection, candidate_hash: str) -> EvidenceDependencyDeclaration:
    row = conn.execute("SELECT dependency_json FROM multi_evidence_dependency WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("multi-hypothesis update requires dependency declaration")
    return dependency_from_dict(json.loads(row[0]))


def _rule(conn: sqlite3.Connection, candidate_hash: str) -> MultiEvidenceRule:
    row = conn.execute("SELECT rule_json FROM multi_evidence_rule WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("multi-hypothesis update requires evidence interpretation rule")
    return rule_from_dict(json.loads(row[0]))


def _accepted_evidence(conn: sqlite3.Connection, evidence_hash: str) -> MultiEvidenceReceipt:
    row = conn.execute("SELECT receipt_json FROM multi_evidence_history WHERE evidence_hash=?", (evidence_hash,)).fetchone()
    if row is None:
        raise ValueError("referenced parent evidence is not accepted evidence")
    return evidence_from_dict(json.loads(row[0]))


def action_register_distribution(distribution: HypothesisDistribution) -> dict[str, object]:
    distribution.validate()
    return {
        "operation": "register_distribution",
        "distribution_ref": distribution.distribution_ref,
        "subject_identity_ref": distribution.subject_identity_ref,
        "distribution_hash": distribution.distribution_hash,
        "generation": distribution.generation,
    }


def action_register_multi_model(model: MultiLikelihoodModel, distribution_ref: str, subject_identity_ref: str) -> dict[str, object]:
    model.validate()
    return {
        "operation": "register_multi_likelihood_model",
        "candidate_hash": model.candidate_hash,
        "distribution_ref": distribution_ref,
        "distribution_hash": model.distribution_hash,
        "model_hash": model.model_hash,
        "subject_identity_ref": subject_identity_ref,
        "model_generation": model.model_generation,
    }


def action_register_dependency(value: EvidenceDependencyDeclaration, subject_identity_ref: str) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_evidence_dependency",
        "candidate_hash": value.candidate_hash,
        "dependency_hash": value.dependency_hash,
        "source_event_hash": value.source_event_hash,
        "dependency_group_ref": value.dependency_group_ref,
        "mode": value.mode,
        "subject_identity_ref": subject_identity_ref,
        "declaration_generation": value.declaration_generation,
    }


def action_register_rule(value: MultiEvidenceRule, subject_identity_ref: str) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_multi_evidence_rule",
        "candidate_hash": value.candidate_hash,
        "likelihood_model_hash": value.likelihood_model_hash,
        "rule_hash": value.rule_hash,
        "subject_identity_ref": subject_identity_ref,
        "rule_generation": value.rule_generation,
    }


def action_apply_multi_update(
    *,
    state_hash: str,
    evidence_hash: str,
    disposition: str,
    result_hash: str,
    posterior_distribution_hash: str | None,
    rebase_hashes: tuple[str, ...],
    applied_at: int,
) -> dict[str, object]:
    return {
        "operation": "apply_multi_update",
        "state_hash": state_hash,
        "evidence_hash": evidence_hash,
        "disposition": disposition,
        "result_hash": result_hash,
        "posterior_distribution_hash": posterior_distribution_hash,
        "rebase_hashes": list(rebase_hashes),
        "applied_at": applied_at,
    }


def _register_distribution(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> HypothesisDistribution:
    probabilities = {str(key): int(value) for key, value in _mapping(payload["probability_bps"], "probability_bps").items()}
    distribution = make_hypothesis_distribution(
        str(payload["distribution_ref"]),
        subject_identity_ref=str(payload["subject_identity_ref"]),
        probability_bps=probabilities,
        evidence_state_hash=str(payload["evidence_state_hash"]),
        generation=int(payload["generation"]),
    )
    _enforce(
        grant,
        proof,
        action=action_register_distribution(distribution),
        required_role=ROLE_MULTI_MODEL_KEEPER,
        required_scope=verification_scope(distribution.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute(
        "SELECT distribution_json FROM multi_hypothesis_distribution WHERE distribution_ref=?",
        (distribution.distribution_ref,),
    ).fetchone()
    encoded = json.dumps(distribution_to_dict(distribution), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = distribution_from_dict(json.loads(existing[0]))
        if current == distribution:
            return current
        raise ValueError("distribution already initialized; advance it only through evidence update")
    conn.execute(
        "INSERT INTO multi_hypothesis_distribution(distribution_ref,distribution_json) VALUES(?,?)",
        (distribution.distribution_ref, encoded),
    )
    return distribution


def _register_model(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> MultiLikelihoodModel:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _candidate_by_hash(conn, candidate_hash)
    distribution_ref = str(payload["distribution_ref"])
    distribution = _distribution(conn, distribution_ref)
    if distribution.subject_identity_ref != candidate.subject_identity_ref:
        raise ValueError("candidate/distribution identity mismatch")
    conditioning = tuple(sorted(str(value) for value in payload.get("conditioning_evidence_hashes", [])))
    for evidence_hash in conditioning:
        _accepted_evidence(conn, evidence_hash)
    likelihoods = {str(key): int(value) for key, value in _mapping(payload["positive_likelihood_bps"], "positive_likelihood_bps").items()}
    model = make_multi_likelihood_model(
        candidate_hash=candidate_hash,
        distribution=distribution,
        positive_likelihood_bps=likelihoods,
        conditioning_evidence_hashes=conditioning,
        model_ref=str(payload["model_ref"]),
        model_generation=int(payload["model_generation"]),
    )
    _enforce(
        grant,
        proof,
        action=action_register_multi_model(model, distribution_ref, candidate.subject_identity_ref),
        required_role=ROLE_MULTI_MODEL_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing_binding = conn.execute("SELECT distribution_ref FROM multi_candidate_binding WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if existing_binding is not None and str(existing_binding[0]) != distribution_ref:
        raise ValueError("candidate already bound to different distribution")
    existing = conn.execute("SELECT model_json FROM multi_likelihood_model WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    encoded = json.dumps(model_to_dict(model), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = model_from_dict(json.loads(existing[0]))
        if current == model:
            return current
        if model.model_generation <= current.model_generation:
            raise ValueError("multi likelihood model generation must advance monotonically")
        conn.execute("UPDATE multi_likelihood_model SET model_json=? WHERE candidate_hash=?", (encoded, candidate_hash))
    else:
        conn.execute("INSERT INTO multi_likelihood_model(candidate_hash,model_json) VALUES(?,?)", (candidate_hash, encoded))
    conn.execute(
        "INSERT INTO multi_candidate_binding(candidate_hash,distribution_ref) VALUES(?,?) ON CONFLICT(candidate_hash) DO NOTHING",
        (candidate_hash, distribution_ref),
    )
    return model


def _ensure_work_incomplete(conn: sqlite3.Connection, candidate_hash: str):
    candidate = _candidate_by_hash(conn, candidate_hash)
    row = conn.execute("SELECT completion_json FROM verification_work WHERE work_hash=?", (candidate.work_hash,)).fetchone()
    if row is None:
        raise ValueError("candidate verification work does not exist")
    if row[0] is not None:
        raise ValueError("evidence semantics must be registered before verification completion")
    return candidate


def _register_dependency(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> EvidenceDependencyDeclaration:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _ensure_work_incomplete(conn, candidate_hash)
    parents = tuple(sorted(str(value) for value in payload.get("parent_evidence_hashes", [])))
    parent_receipts = tuple(_accepted_evidence(conn, value) for value in parents)
    dependency = make_evidence_dependency(
        candidate_hash=candidate_hash,
        source_event_hash=str(payload["source_event_hash"]),
        derivation_hash=str(payload["derivation_hash"]),
        dependency_group_ref=str(payload["dependency_group_ref"]),
        mode=str(payload["mode"]),
        parent_evidence_hashes=parents,
        declaration_ref=str(payload["declaration_ref"]),
        declaration_generation=int(payload["declaration_generation"]),
        declared_at=enforcement.now,
    )
    if dependency.mode == "DUPLICATE":
        if parent_receipts[0].source_event_hash != dependency.source_event_hash:
            raise ValueError("duplicate dependency must preserve parent source_event_hash")
    elif conn.execute("SELECT 1 FROM multi_evidence_history WHERE source_event_hash=?", (dependency.source_event_hash,)).fetchone() is not None:
        raise ValueError("source event already counted as accepted evidence")
    _enforce(
        grant,
        proof,
        action=action_register_dependency(dependency, candidate.subject_identity_ref),
        required_role=ROLE_DEPENDENCY_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT dependency_json FROM multi_evidence_dependency WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    encoded = json.dumps(dependency_to_dict(dependency), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = dependency_from_dict(json.loads(existing[0]))
        if current == dependency:
            return current
        if dependency.declaration_generation <= current.declaration_generation:
            raise ValueError("dependency declaration generation must advance monotonically")
        conn.execute("UPDATE multi_evidence_dependency SET dependency_json=? WHERE candidate_hash=?", (encoded, candidate_hash))
        return dependency
    conn.execute("INSERT INTO multi_evidence_dependency(candidate_hash,dependency_json) VALUES(?,?)", (candidate_hash, encoded))
    return dependency


def _register_rule(
    conn: sqlite3.Connection,
    payload: Mapping[str, object],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> MultiEvidenceRule:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _ensure_work_incomplete(conn, candidate_hash)
    model = _model(conn, candidate_hash)
    distribution = _distribution_for_candidate(conn, candidate_hash)
    if model.distribution_hash != distribution.distribution_hash:
        raise ValueError("multi evidence rule requires current distribution/model binding")
    rule = make_multi_evidence_rule(
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
        action=action_register_rule(rule, candidate.subject_identity_ref),
        required_role=ROLE_MULTI_RULE_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT rule_json FROM multi_evidence_rule WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    encoded = json.dumps(rule_to_dict(rule), sort_keys=True, separators=(",", ":"))
    if existing is not None:
        current = rule_from_dict(json.loads(existing[0]))
        if current == rule:
            return current
        if rule.rule_generation <= current.rule_generation:
            raise ValueError("multi evidence rule generation must advance monotonically")
        conn.execute("UPDATE multi_evidence_rule SET rule_json=? WHERE candidate_hash=?", (encoded, candidate_hash))
        return rule
    conn.execute("INSERT INTO multi_evidence_rule(candidate_hash,rule_json) VALUES(?,?)", (candidate_hash, encoded))
    return rule


def _preview_update(conn: sqlite3.Connection, candidate_hash: str, *, updater_ref: str, now: int) -> dict[str, object]:
    if not updater_ref:
        raise ValueError("updater_ref is required")
    candidate = _candidate_by_hash(conn, candidate_hash)
    distribution = _distribution_for_candidate(conn, candidate_hash)
    model = _model(conn, candidate_hash)
    dependency = _dependency(conn, candidate_hash)
    rule = _rule(conn, candidate_hash)
    completion = _completion(conn, candidate.work_hash)
    evidence = interpret_multi_completion(
        candidate_hash=candidate_hash,
        work_hash=candidate.work_hash,
        completion_hash=completion.completion_hash,
        completion_decision=completion.decision,
        distribution=distribution,
        likelihood_model=model,
        dependency=dependency,
        rule=rule,
        completion_completed_at=completion.completed_at,
        interpreted_at=now,
    )
    parent_receipts = tuple(_accepted_evidence(conn, value) for value in dependency.parent_evidence_hashes)
    source_already_counted = conn.execute(
        "SELECT evidence_hash FROM multi_evidence_history WHERE source_event_hash=?",
        (dependency.source_event_hash,),
    ).fetchone()
    cohort_rows = conn.execute("SELECT candidate_hash,model_json FROM multi_likelihood_model ORDER BY candidate_hash").fetchall()
    cohort_models = []
    for cohort_candidate_hash, model_json in cohort_rows:
        cohort_model = model_from_dict(json.loads(model_json))
        if cohort_model.distribution_hash == distribution.distribution_hash:
            cohort_models.append((str(cohort_candidate_hash), cohort_model))

    if dependency.mode == "DUPLICATE":
        if not parent_receipts:
            raise ValueError("duplicate evidence parent is missing")
        duplicate = build_duplicate_evidence_receipt(
            evidence,
            parent_source_event_hash=parent_receipts[0].source_event_hash,
            observed_at=now,
        )
        disposition = "DUPLICATE_NO_UPDATE"
        posterior = None
        update = None
        rebased_models = ()
        rebases = ()
        result_hash = duplicate.duplicate_hash
    else:
        if source_already_counted is not None:
            raise ValueError("source event has already been counted; declare duplicate evidence explicitly")
        if dependency.mode == "CONDITIONAL":
            if model.conditioning_evidence_hashes != dependency.parent_evidence_hashes:
                raise ValueError("conditional evidence requires exact conditional likelihood context")
        elif model.conditioning_evidence_hashes:
            raise ValueError("independent evidence cannot use conditional likelihood")
        posterior, update = build_multi_hypothesis_update(
            distribution=distribution,
            likelihood_model=model,
            evidence=evidence,
            applied_at=now,
            updater_ref=updater_ref,
        )
        rebased_models_list = []
        rebases_list = []
        for cohort_candidate_hash, cohort_model in cohort_models:
            rebased, rebase = rebase_multi_likelihood_model(
                cohort_model,
                posterior_distribution=posterior,
                rebased_at=now,
            )
            rebased_models_list.append((cohort_candidate_hash, rebased))
            rebases_list.append(rebase)
        rebased_models = tuple(rebased_models_list)
        rebases = tuple(rebases_list)
        duplicate = None
        disposition = "UPDATE"
        result_hash = update.update_hash

    state_material = {
        "domain": "ATMAN-LATTICE/runtime-multi-evidence-state/v1.11",
        "candidate_hash": candidate_hash,
        "completion_hash": completion.completion_hash,
        "distribution_hash": distribution.distribution_hash,
        "model_hash": model.model_hash,
        "dependency_hash": dependency.dependency_hash,
        "rule_hash": rule.rule_hash,
        "parent_evidence_hashes": list(dependency.parent_evidence_hashes),
        "parent_source_event_hashes": [item.source_event_hash for item in parent_receipts],
        "source_already_counted_evidence_hash": None if source_already_counted is None else str(source_already_counted[0]),
        "cohort_model_hashes": sorted(item[1].model_hash for item in cohort_models),
    }
    insight = multi_expected_information_gain(distribution, model, computed_at=now)
    return {
        "state_hash": _digest(state_material),
        "candidate": candidate,
        "distribution": distribution,
        "model": model,
        "dependency": dependency,
        "rule": rule,
        "completion": completion,
        "evidence": evidence,
        "parent_receipts": parent_receipts,
        "disposition": disposition,
        "posterior": posterior,
        "update": update,
        "duplicate": duplicate,
        "rebased_models": rebased_models,
        "rebases": rebases,
        "result_hash": result_hash,
        "insight": insight,
    }


def execute_multi_request(
    request: Mapping[str, object],
    *,
    enforcement: EnforcementContext,
    db_path: str,
) -> dict[str, object]:
    if request.get("protocol") != MULTI_PROTOCOL:
        raise ValueError("unsupported multi-hypothesis protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in MULTI_OPERATIONS:
        raise ValueError("unsupported multi-hypothesis operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_multi_state":
            distribution = _distribution(conn, str(payload["distribution_ref"]))
            accepted_count = int(conn.execute("SELECT COUNT(*) FROM multi_evidence_history").fetchone()[0])
            duplicate_count = int(conn.execute("SELECT COUNT(*) FROM multi_duplicate_history").fetchone()[0])
            return {
                "protocol": MULTI_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "distribution": distribution_to_dict(distribution),
                "accepted_evidence_count": accepted_count,
                "duplicate_evidence_count": duplicate_count,
            }

        if operation == "preview_multi_update":
            preview = _preview_update(
                conn,
                str(payload["candidate_hash"]),
                updater_ref=str(payload["updater_ref"]),
                now=enforcement.now,
            )
            response = {
                "protocol": MULTI_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "state_hash": preview["state_hash"],
                "disposition": preview["disposition"],
                "evidence": evidence_to_dict(preview["evidence"]),
                "result_hash": preview["result_hash"],
                "information_gain": asdict(preview["insight"]),
                "rebases": [rebase_to_dict(item) for item in preview["rebases"]],
            }
            if preview["posterior"] is not None:
                response["posterior_distribution"] = distribution_to_dict(preview["posterior"])
                response["update"] = update_to_dict(preview["update"])
            else:
                response["duplicate"] = duplicate_to_dict(preview["duplicate"])
            return response

        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")

        if operation == "register_distribution":
            value = _register_distribution(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": MULTI_PROTOCOL, "request_id": request_id, "ok": True, "distribution": distribution_to_dict(value)}
        if operation == "register_multi_likelihood_model":
            value = _register_model(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": MULTI_PROTOCOL, "request_id": request_id, "ok": True, "likelihood_model": model_to_dict(value)}
        if operation == "register_evidence_dependency":
            value = _register_dependency(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": MULTI_PROTOCOL, "request_id": request_id, "ok": True, "dependency": dependency_to_dict(value)}
        if operation == "register_multi_evidence_rule":
            value = _register_rule(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": MULTI_PROTOCOL, "request_id": request_id, "ok": True, "rule": rule_to_dict(value)}

        candidate_hash = str(payload["candidate_hash"])
        expected_state_hash = str(payload.get("expected_state_hash", ""))
        expected_evidence_hash = str(payload.get("expected_evidence_hash", ""))
        expected_result_hash = str(payload.get("expected_result_hash", ""))
        if not expected_state_hash or not expected_evidence_hash or not expected_result_hash:
            raise ValueError("expected state, evidence, and result hashes are required")
        preview = _preview_update(conn, candidate_hash, updater_ref=grant.subject_ref, now=enforcement.now)
        if preview["state_hash"] != expected_state_hash:
            raise PermissionError("stale multi-hypothesis evidence state")
        if preview["evidence"].evidence_hash != expected_evidence_hash or preview["result_hash"] != expected_result_hash:
            raise PermissionError("stale multi-hypothesis evidence result")
        rebase_hashes = tuple(sorted(item.rebase_hash for item in preview["rebases"]))
        action = action_apply_multi_update(
            state_hash=preview["state_hash"],
            evidence_hash=preview["evidence"].evidence_hash,
            disposition=preview["disposition"],
            result_hash=preview["result_hash"],
            posterior_distribution_hash=None if preview["posterior"] is None else preview["posterior"].distribution_hash,
            rebase_hashes=rebase_hashes,
            applied_at=enforcement.now,
        )
        _enforce(
            grant,
            proof,
            action=action,
            required_role=ROLE_MULTI_UPDATE_KEEPER,
            required_scope=verification_scope(preview["candidate"].subject_identity_ref),
            enforcement=enforcement,
        )
        completion_hash = preview["completion"].completion_hash
        if conn.execute("SELECT 1 FROM multi_evidence_history WHERE completion_hash=?", (completion_hash,)).fetchone() is not None:
            raise ValueError("verification completion already counted as multi evidence")
        if conn.execute("SELECT 1 FROM multi_duplicate_history WHERE completion_hash=?", (completion_hash,)).fetchone() is not None:
            raise ValueError("verification completion already recorded as duplicate evidence")

        if preview["disposition"] == "DUPLICATE_NO_UPDATE":
            duplicate = preview["duplicate"]
            conn.execute(
                "INSERT INTO multi_duplicate_history(duplicate_hash,evidence_hash,completion_hash,receipt_json) VALUES(?,?,?,?)",
                (
                    duplicate.duplicate_hash,
                    preview["evidence"].evidence_hash,
                    completion_hash,
                    json.dumps(duplicate_to_dict(duplicate), sort_keys=True, separators=(",", ":")),
                ),
            )
            conn.execute("COMMIT")
            return {
                "protocol": MULTI_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "disposition": preview["disposition"],
                "state_hash": preview["state_hash"],
                "evidence": evidence_to_dict(preview["evidence"]),
                "duplicate": duplicate_to_dict(duplicate),
            }

        if conn.execute("SELECT 1 FROM multi_evidence_history WHERE source_event_hash=?", (preview["evidence"].source_event_hash,)).fetchone() is not None:
            raise ValueError("source event already counted as evidence")
        if conn.execute("SELECT 1 FROM multi_update_history WHERE prior_distribution_hash=?", (preview["distribution"].distribution_hash,)).fetchone() is not None:
            raise ValueError("prior multi-hypothesis distribution already advanced")
        posterior = preview["posterior"]
        distribution_ref = preview["distribution"].distribution_ref
        conn.execute(
            "UPDATE multi_hypothesis_distribution SET distribution_json=? WHERE distribution_ref=?",
            (json.dumps(distribution_to_dict(posterior), sort_keys=True, separators=(",", ":")), distribution_ref),
        )
        for cohort_candidate_hash, rebased in preview["rebased_models"]:
            conn.execute(
                "UPDATE multi_likelihood_model SET model_json=? WHERE candidate_hash=?",
                (json.dumps(model_to_dict(rebased), sort_keys=True, separators=(",", ":")), cohort_candidate_hash),
            )
        conn.execute(
            "INSERT INTO multi_evidence_history(evidence_hash,candidate_hash,completion_hash,source_event_hash,dependency_group_ref,receipt_json) VALUES(?,?,?,?,?,?)",
            (
                preview["evidence"].evidence_hash,
                candidate_hash,
                completion_hash,
                preview["evidence"].source_event_hash,
                preview["evidence"].dependency_group_ref,
                json.dumps(evidence_to_dict(preview["evidence"]), sort_keys=True, separators=(",", ":")),
            ),
        )
        conn.execute(
            "INSERT INTO multi_update_history(update_hash,candidate_hash,prior_distribution_hash,receipt_json) VALUES(?,?,?,?)",
            (
                preview["update"].update_hash,
                candidate_hash,
                preview["distribution"].distribution_hash,
                json.dumps(update_to_dict(preview["update"]), sort_keys=True, separators=(",", ":")),
            ),
        )
        for rebase in preview["rebases"]:
            conn.execute(
                "INSERT INTO multi_likelihood_rebase_history(rebase_hash,candidate_hash,receipt_json) VALUES(?,?,?)",
                (rebase.rebase_hash, rebase.candidate_hash, json.dumps(rebase_to_dict(rebase), sort_keys=True, separators=(",", ":"))),
            )
        conn.execute("COMMIT")
        return {
            "protocol": MULTI_PROTOCOL,
            "request_id": request_id,
            "ok": True,
            "disposition": preview["disposition"],
            "state_hash": preview["state_hash"],
            "evidence": evidence_to_dict(preview["evidence"]),
            "posterior_distribution": distribution_to_dict(posterior),
            "update": update_to_dict(preview["update"]),
            "rebases": [rebase_to_dict(item) for item in preview["rebases"]],
        }
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
