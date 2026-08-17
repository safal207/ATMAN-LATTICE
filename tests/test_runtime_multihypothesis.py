import json
import os
import sqlite3
import subprocess
import sys
from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.multihypothesis import (
    make_evidence_dependency,
    make_hypothesis_distribution,
    make_multi_evidence_rule,
    make_multi_likelihood_model,
)
from model.runtime_economy import candidate_to_dict
from model.runtime_multihypothesis import (
    MULTI_PROTOCOL,
    ROLE_DEPENDENCY_KEEPER,
    ROLE_MULTI_MODEL_KEEPER,
    ROLE_MULTI_RULE_KEEPER,
    ROLE_MULTI_UPDATE_KEEPER,
    action_apply_multi_update,
    action_register_dependency,
    action_register_distribution,
    action_register_multi_model,
    action_register_rule,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_verification import (
    VerificationCompletionReceipt,
    _digest as verification_digest,
    completion_to_dict,
    verification_scope,
    work_to_dict,
)
from model.verification_economy import make_economic_candidate
from model.verification_pressure import make_verification_work

IDENTITY = "agent:multi-runtime"
MODEL_NOW = 120
SEMANTICS_NOW = 150
COMPLETED_AT = 200
APPLY_NOW = 250


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture():
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:multi",
        subject_ref="multi-keeper",
        subject_key_id="multi-key",
        subject_public_key=actor.public_key(),
        roles=(
            ROLE_MULTI_MODEL_KEEPER,
            ROLE_DEPENDENCY_KEEPER,
            ROLE_MULTI_RULE_KEEPER,
            ROLE_MULTI_UPDATE_KEEPER,
        ),
        scopes=(verification_scope(IDENTITY),),
        policy_generation=12,
        valid_from=100,
        valid_until=1000,
        issuer_ref="root",
        issuer_key_id="root-key",
        issuer_private_key=root,
    )
    return root, actor, grant


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run(
        [sys.executable, "-m", "model.multi_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def initialize_db(db_path):
    works = []
    candidates = []
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE verification_work (
            work_hash TEXT PRIMARY KEY,
            work_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            target_gate_hash TEXT NOT NULL,
            work_json TEXT NOT NULL,
            status TEXT NOT NULL,
            completion_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE verification_economy_candidate (
            work_hash TEXT PRIMARY KEY,
            candidate_json TEXT NOT NULL
        )
        """
    )
    for index, name in enumerate(("a", "b", "c")):
        work = make_verification_work(
            f"work:multi:{name}",
            subject_identity_ref=IDENTITY,
            evidence={"kind": f"check-{name}"},
            cost_units=1,
            priority=0,
            submitted_at=100 + index,
        )
        candidate = make_economic_candidate(
            work_hash=work.work_hash,
            subject_identity_ref=IDENTITY,
            estimator_key="multi",
            declared_cost_units=1,
            value_units=10,
            risk_units=5,
            priority=0,
            submitted_at=100 + index,
        )
        conn.execute(
            "INSERT INTO verification_work(work_hash,work_ref,subject_identity_ref,target_gate_hash,work_json,status,completion_json) VALUES(?,?,?,?,?,?,NULL)",
            (work.work_hash, work.work_ref, IDENTITY, chr(ord("a") + index) * 64, json.dumps(work_to_dict(work)), "SUBMITTED"),
        )
        conn.execute(
            "INSERT INTO verification_economy_candidate(work_hash,candidate_json) VALUES(?,?)",
            (work.work_hash, json.dumps(candidate_to_dict(candidate))),
        )
        works.append(work)
        candidates.append(candidate)
    conn.commit()
    conn.close()
    return tuple(works), tuple(candidates)


def complete_work(db_path, work, *, decision="PASS"):
    suffix = work.work_ref.rsplit(":", 1)[-1]
    gate = suffix * 64
    fields = {
        "work_hash": work.work_hash,
        "subject_identity_ref": IDENTITY,
        "target_gate_hash": gate,
        "schedule_generation": 1,
        "pressure_hash": "d" * 64,
        "decision": decision,
        "evidence_digest": "e" * 64,
        "completed_at": COMPLETED_AT,
        "actor_ref": "verification-executor",
    }
    provisional = VerificationCompletionReceipt(**fields, completion_hash="0" * 64)
    receipt = VerificationCompletionReceipt(**fields, completion_hash=verification_digest(provisional.material()))
    receipt.validate()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE verification_work SET status='COMPLETED', completion_json=? WHERE work_hash=?",
        (json.dumps(completion_to_dict(receipt)), work.work_hash),
    )
    conn.commit()
    conn.close()
    return receipt


def distribution_request(*, actor, grant):
    dist = make_hypothesis_distribution(
        "dist:root-cause",
        subject_identity_ref=IDENTITY,
        probability_bps={"H:A": 4000, "H:B": 3500, "H:C": 2500},
        evidence_state_hash=h("evidence:initial"),
        generation=1,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_MULTI_MODEL_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_distribution(dist),
        signed_at=MODEL_NOW,
    )
    request = {
        "protocol": MULTI_PROTOCOL,
        "request_id": "distribution",
        "operation": "register_distribution",
        "payload": {
            "distribution_ref": dist.distribution_ref,
            "subject_identity_ref": dist.subject_identity_ref,
            "probability_bps": dict(dist.probability_bps),
            "evidence_state_hash": dist.evidence_state_hash,
            "generation": dist.generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return dist, request


def model_request(candidate, dist, *, actor, grant, generation=1, conditioning=(), likelihoods=None):
    likelihoods = likelihoods or {"H:A": 9000, "H:B": 2000, "H:C": 1000}
    model = make_multi_likelihood_model(
        candidate_hash=candidate.candidate_hash,
        distribution=dist,
        positive_likelihood_bps=likelihoods,
        conditioning_evidence_hashes=conditioning,
        model_ref=f"model:{candidate.work_hash[:8]}",
        model_generation=generation,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_MULTI_MODEL_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_multi_model(model, dist.distribution_ref, IDENTITY),
        signed_at=MODEL_NOW if generation == 1 else APPLY_NOW,
    )
    request = {
        "protocol": MULTI_PROTOCOL,
        "request_id": f"model:{candidate.candidate_hash[:8]}",
        "operation": "register_multi_likelihood_model",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "distribution_ref": dist.distribution_ref,
            "positive_likelihood_bps": dict(model.positive_likelihood_bps),
            "conditioning_evidence_hashes": list(conditioning),
            "model_ref": model.model_ref,
            "model_generation": generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return model, request


def dependency_request(candidate, *, actor, grant, source_event_hash, mode="INDEPENDENT", parents=(), generation=1, now=SEMANTICS_NOW):
    dep = make_evidence_dependency(
        candidate_hash=candidate.candidate_hash,
        source_event_hash=source_event_hash,
        derivation_hash=h(f"derive:{candidate.candidate_hash}:{generation}"),
        dependency_group_ref="group:root-cause",
        mode=mode,
        parent_evidence_hashes=parents,
        declaration_ref=f"dependency:{candidate.candidate_hash[:8]}",
        declaration_generation=generation,
        declared_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_DEPENDENCY_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_dependency(dep, IDENTITY),
        signed_at=now,
    )
    request = {
        "protocol": MULTI_PROTOCOL,
        "request_id": f"dep:{candidate.candidate_hash[:8]}",
        "operation": "register_evidence_dependency",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "source_event_hash": dep.source_event_hash,
            "derivation_hash": dep.derivation_hash,
            "dependency_group_ref": dep.dependency_group_ref,
            "mode": dep.mode,
            "parent_evidence_hashes": list(dep.parent_evidence_hashes),
            "declaration_ref": dep.declaration_ref,
            "declaration_generation": dep.declaration_generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return dep, request


def rule_request(candidate, model, *, actor, grant, generation=1, now=SEMANTICS_NOW):
    rule = make_multi_evidence_rule(
        candidate_hash=candidate.candidate_hash,
        likelihood_model_hash=model.model_hash,
        pass_outcome="POSITIVE",
        hold_outcome="INCONCLUSIVE",
        fail_outcome="NEGATIVE",
        rule_ref=f"rule:{candidate.candidate_hash[:8]}",
        rule_generation=generation,
        registered_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_MULTI_RULE_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_rule(rule, IDENTITY),
        signed_at=now,
    )
    request = {
        "protocol": MULTI_PROTOCOL,
        "request_id": f"rule:{candidate.candidate_hash[:8]}",
        "operation": "register_multi_evidence_rule",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "pass_outcome": rule.pass_outcome,
            "hold_outcome": rule.hold_outcome,
            "fail_outcome": rule.fail_outcome,
            "rule_ref": rule.rule_ref,
            "rule_generation": rule.rule_generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return rule, request


def preview_request(candidate_hash):
    return {
        "protocol": MULTI_PROTOCOL,
        "request_id": "preview",
        "operation": "preview_multi_update",
        "payload": {"candidate_hash": candidate_hash, "updater_ref": "multi-keeper"},
    }


def apply_request(candidate_hash, preview, *, actor, grant):
    rebase_hashes = tuple(sorted(item["rebase_hash"] for item in preview.get("rebases", [])))
    posterior_hash = preview.get("posterior_distribution", {}).get("distribution_hash")
    action = action_apply_multi_update(
        state_hash=preview["state_hash"],
        evidence_hash=preview["evidence"]["evidence_hash"],
        disposition=preview["disposition"],
        result_hash=preview["result_hash"],
        posterior_distribution_hash=posterior_hash,
        rebase_hashes=rebase_hashes,
        applied_at=APPLY_NOW,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_MULTI_UPDATE_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action,
        signed_at=APPLY_NOW,
    )
    return {
        "protocol": MULTI_PROTOCOL,
        "request_id": "apply",
        "operation": "apply_multi_update",
        "payload": {
            "candidate_hash": candidate_hash,
            "expected_state_hash": preview["state_hash"],
            "expected_evidence_hash": preview["evidence"]["evidence_hash"],
            "expected_result_hash": preview["result_hash"],
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def bootstrap_models(db_path, *, root, actor, grant, candidates):
    dist, request = distribution_request(actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=MODEL_NOW)
    assert completed.returncode == 0, response
    models = []
    for candidate in candidates:
        model, request = model_request(candidate, dist, actor=actor, grant=grant)
        completed, response = invoke(request, root=root, db_path=db_path, now=MODEL_NOW)
        assert completed.returncode == 0, response
        models.append(model)
    return dist, tuple(models)


def accept_independent_a(db_path, works, candidates, *, root, actor, grant):
    dist, models = bootstrap_models(db_path, root=root, actor=actor, grant=grant, candidates=candidates)
    source = h("source:event:1")
    _, request = dependency_request(candidates[0], actor=actor, grant=grant, source_event_hash=source)
    completed, response = invoke(request, root=root, db_path=db_path, now=SEMANTICS_NOW)
    assert completed.returncode == 0, response
    _, request = rule_request(candidates[0], models[0], actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=SEMANTICS_NOW)
    assert completed.returncode == 0, response
    complete_work(db_path, works[0], decision="PASS")
    completed, preview = invoke(preview_request(candidates[0].candidate_hash), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, preview
    assert preview["disposition"] == "UPDATE"
    completed, response = invoke(apply_request(candidates[0].candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, response
    return dist, models, source, response


def test_independent_evidence_updates_distribution_and_rebases_cohort_models(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    prior, models, _, response = accept_independent_a(db_path, works, candidates, root=root, actor=actor, grant=grant)
    posterior = response["posterior_distribution"]
    assert posterior["generation"] == prior.generation + 1
    assert dict(posterior["probability_bps"])["H:A"] > 4000
    assert len(response["rebases"]) == 3

    conn = sqlite3.connect(db_path)
    model_b = json.loads(conn.execute("SELECT model_json FROM multi_likelihood_model WHERE candidate_hash=?", (candidates[1].candidate_hash,)).fetchone()[0])
    conn.close()
    assert model_b["distribution_hash"] == posterior["distribution_hash"]
    assert model_b["model_generation"] == models[1].model_generation + 1


def test_duplicate_source_is_recorded_without_second_posterior_update(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    _, _, source, first = accept_independent_a(db_path, works, candidates, root=root, actor=actor, grant=grant)
    parent_evidence = first["evidence"]["evidence_hash"]

    conn = sqlite3.connect(db_path)
    current_dist = json.loads(conn.execute("SELECT distribution_json FROM multi_hypothesis_distribution WHERE distribution_ref='dist:root-cause'").fetchone()[0])
    current_model = json.loads(conn.execute("SELECT model_json FROM multi_likelihood_model WHERE candidate_hash=?", (candidates[1].candidate_hash,)).fetchone()[0])
    conn.close()
    _, dep_request = dependency_request(
        candidates[1], actor=actor, grant=grant, source_event_hash=source, mode="DUPLICATE", parents=(parent_evidence,), now=260
    )
    completed, response = invoke(dep_request, root=root, db_path=db_path, now=260)
    assert completed.returncode == 0, response
    from model.runtime_multihypothesis import model_from_dict
    model_b = model_from_dict(current_model)
    _, req = rule_request(candidates[1], model_b, actor=actor, grant=grant, generation=2, now=260)
    completed, response = invoke(req, root=root, db_path=db_path, now=260)
    assert completed.returncode == 0, response
    complete_work(db_path, works[1], decision="PASS")
    completed, preview = invoke(preview_request(candidates[1].candidate_hash), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, preview
    assert preview["disposition"] == "DUPLICATE_NO_UPDATE"
    completed, response = invoke(apply_request(candidates[1].candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, response

    completed, state = invoke(
        {"protocol": MULTI_PROTOCOL, "request_id": "state", "operation": "get_multi_state", "payload": {"distribution_ref": "dist:root-cause"}},
        root=root, db_path=db_path, now=APPLY_NOW,
    )
    assert completed.returncode == 0, state
    assert state["distribution"]["distribution_hash"] == current_dist["distribution_hash"]
    assert state["accepted_evidence_count"] == 1
    assert state["duplicate_evidence_count"] == 1


def test_same_source_cannot_be_redeclared_independent_after_it_was_counted(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    _, _, source, _ = accept_independent_a(db_path, works, candidates, root=root, actor=actor, grant=grant)
    _, request = dependency_request(candidates[1], actor=actor, grant=grant, source_event_hash=source, mode="INDEPENDENT", now=260)
    completed, response = invoke(request, root=root, db_path=db_path, now=260)
    assert completed.returncode == 2
    assert "already counted" in response["error"]


def test_conditional_evidence_requires_parent_bound_likelihood_and_can_update(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    _, _, _, first = accept_independent_a(db_path, works, candidates, root=root, actor=actor, grant=grant)
    parent = first["evidence"]["evidence_hash"]

    completed, state = invoke(
        {"protocol": MULTI_PROTOCOL, "request_id": "state", "operation": "get_multi_state", "payload": {"distribution_ref": "dist:root-cause"}},
        root=root, db_path=db_path, now=260,
    )
    assert completed.returncode == 0, state
    dist = make_hypothesis_distribution(
        state["distribution"]["distribution_ref"],
        subject_identity_ref=state["distribution"]["subject_identity_ref"],
        probability_bps=dict(state["distribution"]["probability_bps"]),
        evidence_state_hash=state["distribution"]["evidence_state_hash"],
        generation=state["distribution"]["generation"],
    )
    conditional_model, request = model_request(
        candidates[2], dist, actor=actor, grant=grant, generation=3, conditioning=(parent,), likelihoods={"H:A": 6000, "H:B": 9000, "H:C": 2000}
    )
    completed, response = invoke(request, root=root, db_path=db_path, now=260)
    assert completed.returncode == 0, response
    _, request = dependency_request(
        candidates[2], actor=actor, grant=grant, source_event_hash=h("source:event:2"), mode="CONDITIONAL", parents=(parent,), generation=2, now=260
    )
    completed, response = invoke(request, root=root, db_path=db_path, now=260)
    assert completed.returncode == 0, response
    _, request = rule_request(candidates[2], conditional_model, actor=actor, grant=grant, generation=2, now=260)
    completed, response = invoke(request, root=root, db_path=db_path, now=260)
    assert completed.returncode == 0, response
    complete_work(db_path, works[2], decision="PASS")
    completed, preview = invoke(preview_request(candidates[2].candidate_hash), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, preview
    assert preview["disposition"] == "UPDATE"
    completed, response = invoke(apply_request(candidates[2].candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, response
    assert response["posterior_distribution"]["generation"] == dist.generation + 1


def test_dependency_keeper_role_is_not_replaceable_by_model_role(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    dist, models = bootstrap_models(db_path, root=root, actor=actor, grant=grant, candidates=candidates)
    dep = make_evidence_dependency(
        candidate_hash=candidates[0].candidate_hash,
        source_event_hash=h("role-source"),
        derivation_hash=h("role-derivation"),
        dependency_group_ref="group:root-cause",
        mode="INDEPENDENT",
        declaration_ref="dependency:role",
        declaration_generation=1,
        declared_at=SEMANTICS_NOW,
    )
    wrong_proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_MULTI_MODEL_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_dependency(dep, IDENTITY),
        signed_at=SEMANTICS_NOW,
    )
    request = {
        "protocol": MULTI_PROTOCOL,
        "request_id": "wrong-role",
        "operation": "register_evidence_dependency",
        "payload": {
            "candidate_hash": candidates[0].candidate_hash,
            "source_event_hash": dep.source_event_hash,
            "derivation_hash": dep.derivation_hash,
            "dependency_group_ref": dep.dependency_group_ref,
            "mode": dep.mode,
            "parent_evidence_hashes": [],
            "declaration_ref": dep.declaration_ref,
            "declaration_generation": dep.declaration_generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(wrong_proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=SEMANTICS_NOW)
    assert completed.returncode == 2
    assert "required_role_mismatch" in response["error"]
