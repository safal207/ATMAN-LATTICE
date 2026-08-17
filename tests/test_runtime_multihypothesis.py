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
    model_from_dict,
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
INIT_AT = 120
SEM1_AT = 150
COMPLETE1_AT = 200
APPLY1_AT = 250
SEM2_AT = 300
COMPLETE2_AT = 350
APPLY2_AT = 400


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
        roles=(ROLE_MULTI_MODEL_KEEPER, ROLE_DEPENDENCY_KEEPER, ROLE_MULTI_RULE_KEEPER, ROLE_MULTI_UPDATE_KEEPER),
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
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)"
    )
    conn.execute(
        "CREATE TABLE verification_economy_candidate (work_hash TEXT PRIMARY KEY, candidate_json TEXT NOT NULL)"
    )
    works, candidates = [], []
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
            (work.work_hash, work.work_ref, IDENTITY, name * 64, json.dumps(work_to_dict(work)), "SUBMITTED"),
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


def complete_work(db_path, work, *, completed_at, decision="PASS"):
    name = work.work_ref.rsplit(":", 1)[-1]
    fields = {
        "work_hash": work.work_hash,
        "subject_identity_ref": IDENTITY,
        "target_gate_hash": name * 64,
        "schedule_generation": 1,
        "pressure_hash": "d" * 64,
        "decision": decision,
        "evidence_digest": "e" * 64,
        "completed_at": completed_at,
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


def register_distribution(db_path, *, root, actor, grant):
    dist = make_hypothesis_distribution(
        "dist:root-cause",
        subject_identity_ref=IDENTITY,
        probability_bps={"H:A": 4000, "H:B": 3500, "H:C": 2500},
        evidence_state_hash=h("evidence:initial"),
        generation=1,
    )
    proof = sign_authorized_action(
        grant, private_key=actor, role=ROLE_MULTI_MODEL_KEEPER, scope=verification_scope(IDENTITY),
        action=action_register_distribution(dist), signed_at=INIT_AT,
    )
    request = {
        "protocol": MULTI_PROTOCOL, "request_id": "dist", "operation": "register_distribution",
        "payload": {"distribution_ref": dist.distribution_ref, "subject_identity_ref": IDENTITY, "probability_bps": dict(dist.probability_bps), "evidence_state_hash": dist.evidence_state_hash, "generation": dist.generation},
        "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=INIT_AT)
    assert completed.returncode == 0, response
    return dist


def register_model(db_path, candidate, dist, *, root, actor, grant, now, generation, conditioning=(), likelihoods=None):
    likelihoods = likelihoods or {"H:A": 9000, "H:B": 2000, "H:C": 1000}
    model = make_multi_likelihood_model(
        candidate_hash=candidate.candidate_hash,
        distribution=dist,
        positive_likelihood_bps=likelihoods,
        conditioning_evidence_hashes=conditioning,
        model_ref=f"model:{candidate.candidate_hash[:8]}",
        model_generation=generation,
    )
    action = action_register_multi_model(model, dist.distribution_ref, IDENTITY)
    proof = sign_authorized_action(
        grant, private_key=actor, role=ROLE_MULTI_MODEL_KEEPER, scope=verification_scope(IDENTITY), action=action, signed_at=now,
    )
    request = {
        "protocol": MULTI_PROTOCOL, "request_id": "model", "operation": "register_multi_likelihood_model",
        "payload": {"candidate_hash": candidate.candidate_hash, "distribution_ref": dist.distribution_ref, "positive_likelihood_bps": dict(model.positive_likelihood_bps), "conditioning_evidence_hashes": list(conditioning), "model_ref": model.model_ref, "model_generation": generation},
        "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response
    return model


def register_dependency(db_path, candidate, *, root, actor, grant, now, source, mode="INDEPENDENT", parents=(), generation=1, role=ROLE_DEPENDENCY_KEEPER):
    dep = make_evidence_dependency(
        candidate_hash=candidate.candidate_hash,
        source_event_hash=source,
        derivation_hash=h(f"derivation:{candidate.candidate_hash}:{generation}"),
        dependency_group_ref="group:root-cause",
        mode=mode,
        parent_evidence_hashes=parents,
        declaration_ref=f"dep:{candidate.candidate_hash[:8]}",
        declaration_generation=generation,
        declared_at=now,
    )
    proof = sign_authorized_action(
        grant, private_key=actor, role=role, scope=verification_scope(IDENTITY),
        action=action_register_dependency(dep, IDENTITY), signed_at=now,
    )
    request = {
        "protocol": MULTI_PROTOCOL, "request_id": "dep", "operation": "register_evidence_dependency",
        "payload": {"candidate_hash": candidate.candidate_hash, "source_event_hash": dep.source_event_hash, "derivation_hash": dep.derivation_hash, "dependency_group_ref": dep.dependency_group_ref, "mode": dep.mode, "parent_evidence_hashes": list(dep.parent_evidence_hashes), "declaration_ref": dep.declaration_ref, "declaration_generation": generation},
        "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof),
    }
    return invoke(request, root=root, db_path=db_path, now=now)


def register_rule(db_path, candidate, model, *, root, actor, grant, now, generation=1):
    rule = make_multi_evidence_rule(
        candidate_hash=candidate.candidate_hash,
        likelihood_model_hash=model.model_hash,
        pass_outcome="POSITIVE", hold_outcome="INCONCLUSIVE", fail_outcome="NEGATIVE",
        rule_ref=f"rule:{candidate.candidate_hash[:8]}", rule_generation=generation, registered_at=now,
    )
    proof = sign_authorized_action(
        grant, private_key=actor, role=ROLE_MULTI_RULE_KEEPER, scope=verification_scope(IDENTITY),
        action=action_register_rule(rule, IDENTITY), signed_at=now,
    )
    request = {
        "protocol": MULTI_PROTOCOL, "request_id": "rule", "operation": "register_multi_evidence_rule",
        "payload": {"candidate_hash": candidate.candidate_hash, "pass_outcome": "POSITIVE", "hold_outcome": "INCONCLUSIVE", "fail_outcome": "NEGATIVE", "rule_ref": rule.rule_ref, "rule_generation": generation},
        "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response


def preview(db_path, candidate, *, root, now):
    request = {"protocol": MULTI_PROTOCOL, "request_id": "preview", "operation": "preview_multi_update", "payload": {"candidate_hash": candidate.candidate_hash, "updater_ref": "multi-keeper"}}
    return invoke(request, root=root, db_path=db_path, now=now)


def apply_preview(db_path, candidate, preview_response, *, root, actor, grant, now):
    rebase_hashes = tuple(sorted(item["rebase_hash"] for item in preview_response.get("rebases", [])))
    posterior_hash = preview_response.get("posterior_distribution", {}).get("distribution_hash")
    action = action_apply_multi_update(
        state_hash=preview_response["state_hash"], evidence_hash=preview_response["evidence"]["evidence_hash"],
        disposition=preview_response["disposition"], result_hash=preview_response["result_hash"],
        posterior_distribution_hash=posterior_hash, rebase_hashes=rebase_hashes, applied_at=now,
    )
    proof = sign_authorized_action(
        grant, private_key=actor, role=ROLE_MULTI_UPDATE_KEEPER, scope=verification_scope(IDENTITY), action=action, signed_at=now,
    )
    request = {
        "protocol": MULTI_PROTOCOL, "request_id": "apply", "operation": "apply_multi_update",
        "payload": {"candidate_hash": candidate.candidate_hash, "expected_state_hash": preview_response["state_hash"], "expected_evidence_hash": preview_response["evidence"]["evidence_hash"], "expected_result_hash": preview_response["result_hash"]},
        "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof),
    }
    return invoke(request, root=root, db_path=db_path, now=now)


def bootstrap(db_path, *, root, actor, grant, candidates):
    dist = register_distribution(db_path, root=root, actor=actor, grant=grant)
    models = tuple(register_model(db_path, c, dist, root=root, actor=actor, grant=grant, now=INIT_AT, generation=1) for c in candidates)
    return dist, models


def accept_first(db_path, works, candidates, *, root, actor, grant):
    prior, models = bootstrap(db_path, root=root, actor=actor, grant=grant, candidates=candidates)
    source = h("source:event:1")
    completed, response = register_dependency(db_path, candidates[0], root=root, actor=actor, grant=grant, now=SEM1_AT, source=source)
    assert completed.returncode == 0, response
    register_rule(db_path, candidates[0], models[0], root=root, actor=actor, grant=grant, now=SEM1_AT)
    complete_work(db_path, works[0], completed_at=COMPLETE1_AT)
    completed, p = preview(db_path, candidates[0], root=root, now=APPLY1_AT)
    assert completed.returncode == 0, p
    completed, applied = apply_preview(db_path, candidates[0], p, root=root, actor=actor, grant=grant, now=APPLY1_AT)
    assert completed.returncode == 0, applied
    return prior, models, source, applied


def current_distribution(db_path):
    conn = sqlite3.connect(db_path)
    raw = json.loads(conn.execute("SELECT distribution_json FROM multi_hypothesis_distribution WHERE distribution_ref='dist:root-cause'").fetchone()[0])
    conn.close()
    return make_hypothesis_distribution(
        raw["distribution_ref"], subject_identity_ref=raw["subject_identity_ref"],
        probability_bps=dict(raw["probability_bps"]), evidence_state_hash=raw["evidence_state_hash"], generation=raw["generation"],
    )


def current_model(db_path, candidate):
    conn = sqlite3.connect(db_path)
    raw = json.loads(conn.execute("SELECT model_json FROM multi_likelihood_model WHERE candidate_hash=?", (candidate.candidate_hash,)).fetchone()[0])
    conn.close()
    return model_from_dict(raw)


def test_independent_update_rebases_shared_multi_models(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    prior, models, _, applied = accept_first(db_path, works, candidates, root=root, actor=actor, grant=grant)
    posterior = applied["posterior_distribution"]
    assert posterior["generation"] == prior.generation + 1
    assert dict(posterior["probability_bps"])["H:A"] > 4000
    assert len(applied["rebases"]) == 3
    assert current_model(db_path, candidates[1]).model_generation == models[1].model_generation + 1


def test_duplicate_source_is_preserved_without_second_update(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    _, _, source, first = accept_first(db_path, works, candidates, root=root, actor=actor, grant=grant)
    parent = first["evidence"]["evidence_hash"]
    before = current_distribution(db_path)
    model_b = current_model(db_path, candidates[1])
    completed, response = register_dependency(db_path, candidates[1], root=root, actor=actor, grant=grant, now=SEM2_AT, source=source, mode="DUPLICATE", parents=(parent,), generation=2)
    assert completed.returncode == 0, response
    register_rule(db_path, candidates[1], model_b, root=root, actor=actor, grant=grant, now=SEM2_AT, generation=2)
    complete_work(db_path, works[1], completed_at=COMPLETE2_AT)
    completed, p = preview(db_path, candidates[1], root=root, now=APPLY2_AT)
    assert completed.returncode == 0, p
    assert p["disposition"] == "DUPLICATE_NO_UPDATE"
    completed, applied = apply_preview(db_path, candidates[1], p, root=root, actor=actor, grant=grant, now=APPLY2_AT)
    assert completed.returncode == 0, applied
    after = current_distribution(db_path)
    assert after.distribution_hash == before.distribution_hash
    state_request = {"protocol": MULTI_PROTOCOL, "request_id": "state", "operation": "get_multi_state", "payload": {"distribution_ref": "dist:root-cause"}}
    _, state = invoke(state_request, root=root, db_path=db_path, now=APPLY2_AT)
    assert state["accepted_evidence_count"] == 1
    assert state["duplicate_evidence_count"] == 1


def test_counted_source_cannot_be_redeclared_independent_and_dependency_role_is_separate(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    _, _, source, _ = accept_first(db_path, works, candidates, root=root, actor=actor, grant=grant)
    completed, response = register_dependency(db_path, candidates[1], root=root, actor=actor, grant=grant, now=SEM2_AT, source=source)
    assert completed.returncode == 2
    assert "already counted" in response["error"]
    completed, response = register_dependency(db_path, candidates[2], root=root, actor=actor, grant=grant, now=SEM2_AT, source=h("fresh-source"), role=ROLE_MULTI_MODEL_KEEPER)
    assert completed.returncode == 2
    assert "required_role_mismatch" in response["error"]


def test_conditional_update_uses_exact_parent_bound_likelihood(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    works, candidates = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    _, _, _, first = accept_first(db_path, works, candidates, root=root, actor=actor, grant=grant)
    parent = first["evidence"]["evidence_hash"]
    dist = current_distribution(db_path)
    conditional = register_model(
        db_path, candidates[2], dist, root=root, actor=actor, grant=grant, now=SEM2_AT, generation=3,
        conditioning=(parent,), likelihoods={"H:A": 6000, "H:B": 9000, "H:C": 2000},
    )
    completed, response = register_dependency(
        db_path, candidates[2], root=root, actor=actor, grant=grant, now=SEM2_AT,
        source=h("source:event:2"), mode="CONDITIONAL", parents=(parent,), generation=2,
    )
    assert completed.returncode == 0, response
    register_rule(db_path, candidates[2], conditional, root=root, actor=actor, grant=grant, now=SEM2_AT, generation=2)
    complete_work(db_path, works[2], completed_at=COMPLETE2_AT)
    completed, p = preview(db_path, candidates[2], root=root, now=APPLY2_AT)
    assert completed.returncode == 0, p
    assert p["disposition"] == "UPDATE"
    completed, applied = apply_preview(db_path, candidates[2], p, root=root, actor=actor, grant=grant, now=APPLY2_AT)
    assert completed.returncode == 0, applied
    assert applied["posterior_distribution"]["generation"] == dist.generation + 1
