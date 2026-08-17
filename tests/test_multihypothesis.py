from hashlib import sha256

import pytest

from model.multihypothesis import (
    build_duplicate_evidence_receipt,
    build_multi_hypothesis_update,
    interpret_multi_completion,
    make_evidence_dependency,
    make_hypothesis_distribution,
    make_multi_evidence_rule,
    make_multi_likelihood_model,
    multi_expected_information_gain,
    posterior_distribution_bps,
)


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def distribution():
    return make_hypothesis_distribution(
        "dist:root-cause",
        subject_identity_ref="agent:multi",
        probability_bps={"H:A": 4000, "H:B": 3500, "H:C": 2500},
        evidence_state_hash=h("e0"),
        generation=1,
    )


def model(dist=None, *, candidate=h("candidate"), conditioning=()):
    dist = dist or distribution()
    return make_multi_likelihood_model(
        candidate_hash=candidate,
        distribution=dist,
        positive_likelihood_bps={"H:A": 9000, "H:B": 2000, "H:C": 1000},
        conditioning_evidence_hashes=conditioning,
        model_ref="model:multi",
        model_generation=1,
    )


def dependency(*, candidate=h("candidate"), mode="INDEPENDENT", source="source-1", parents=(), declared_at=100):
    return make_evidence_dependency(
        candidate_hash=candidate,
        source_event_hash=h(source),
        derivation_hash=h(source + ":derivation"),
        dependency_group_ref="group:root-cause",
        mode=mode,
        parent_evidence_hashes=parents,
        declaration_ref="dependency:1",
        declaration_generation=1,
        declared_at=declared_at,
    )


def rule(m, *, candidate=h("candidate"), registered_at=100):
    return make_multi_evidence_rule(
        candidate_hash=candidate,
        likelihood_model_hash=m.model_hash,
        pass_outcome="POSITIVE",
        hold_outcome="INCONCLUSIVE",
        fail_outcome="NEGATIVE",
        rule_ref="rule:multi",
        rule_generation=1,
        registered_at=registered_at,
    )


def evidence(*, dist=None, m=None, dep=None, completion_decision="PASS", completed_at=200):
    dist = dist or distribution()
    m = m or model(dist)
    dep = dep or dependency()
    return interpret_multi_completion(
        candidate_hash=m.candidate_hash,
        work_hash=h("work"),
        completion_hash=h("completion"),
        completion_decision=completion_decision,
        distribution=dist,
        likelihood_model=m,
        dependency=dep,
        rule=rule(m, candidate=m.candidate_hash),
        completion_completed_at=completed_at,
        interpreted_at=250,
    )


def test_distribution_requires_normalized_competing_hypotheses():
    with pytest.raises(ValueError, match="sum to 10000"):
        make_hypothesis_distribution(
            "dist:bad",
            subject_identity_ref="agent:multi",
            probability_bps={"A": 5000, "B": 4000},
            evidence_state_hash=h("e"),
            generation=0,
        )


def test_positive_evidence_redistributes_mass_across_three_hypotheses():
    dist = distribution()
    posterior = dict(posterior_distribution_bps(dist, model(dist), "POSITIVE"))
    assert sum(posterior.values()) == 10_000
    assert posterior["H:A"] > 4000
    assert posterior["H:B"] < 3500
    assert posterior["H:C"] < 2500


def test_negative_evidence_can_promote_alternative_explanations():
    dist = distribution()
    posterior = dict(posterior_distribution_bps(dist, model(dist), "NEGATIVE"))
    assert sum(posterior.values()) == 10_000
    assert posterior["H:A"] < 4000
    assert posterior["H:B"] > 3500


def test_uninformative_test_has_zero_expected_information_gain():
    dist = distribution()
    uninformative = make_multi_likelihood_model(
        candidate_hash=h("candidate:flat"),
        distribution=dist,
        positive_likelihood_bps={"H:A": 5000, "H:B": 5000, "H:C": 5000},
        model_ref="model:flat",
        model_generation=1,
    )
    insight = multi_expected_information_gain(dist, uninformative, computed_at=100)
    assert insight.expected_information_gain_microbits == 0


def test_informative_multi_test_has_positive_information_gain():
    dist = distribution()
    insight = multi_expected_information_gain(dist, model(dist), computed_at=100)
    assert insight.expected_information_gain_microbits > 0
    assert insight.expected_posterior_entropy_microbits < insight.prior_entropy_microbits


def test_conditional_dependency_requires_parent_evidence():
    with pytest.raises(ValueError, match="requires parent evidence"):
        dependency(mode="CONDITIONAL")


def test_independent_evidence_cannot_smuggle_conditional_likelihood():
    dist = distribution()
    parent = h("parent")
    conditional_model = model(dist, conditioning=(parent,))
    with pytest.raises(ValueError, match="unconditional likelihood"):
        evidence(dist=dist, m=conditional_model, dep=dependency(mode="INDEPENDENT"))


def test_conditional_likelihood_must_bind_exact_parent_set():
    dist = distribution()
    expected_parent = h("parent:expected")
    wrong_parent = h("parent:wrong")
    conditional_model = model(dist, conditioning=(expected_parent,))
    with pytest.raises(ValueError, match="exact parent evidence"):
        evidence(
            dist=dist,
            m=conditional_model,
            dep=dependency(mode="CONDITIONAL", parents=(wrong_parent,)),
        )


def test_dependency_and_interpretation_must_be_precommitted():
    dist = distribution()
    m = model(dist)
    late = dependency(declared_at=201)
    with pytest.raises(ValueError, match="precommitted"):
        evidence(dist=dist, m=m, dep=late, completed_at=200)


def test_duplicate_evidence_does_not_advance_distribution():
    dist = distribution()
    parent_hash = h("parent:evidence")
    duplicate_dep = dependency(mode="DUPLICATE", parents=(parent_hash,), source="same-source")
    duplicate_evidence = evidence(dist=dist, dep=duplicate_dep)
    duplicate = build_duplicate_evidence_receipt(
        duplicate_evidence,
        parent_source_event_hash=h("same-source"),
        observed_at=260,
    )
    assert duplicate.parent_evidence_hash == parent_hash
    with pytest.raises(ValueError, match="duplicate evidence cannot advance"):
        build_multi_hypothesis_update(
            distribution=dist,
            likelihood_model=model(dist),
            evidence=duplicate_evidence,
            applied_at=260,
            updater_ref="keeper",
        )


def test_duplicate_must_preserve_origin_source_event():
    dist = distribution()
    parent_hash = h("parent:evidence")
    duplicate_evidence = evidence(
        dist=dist,
        dep=dependency(mode="DUPLICATE", parents=(parent_hash,), source="source:new"),
    )
    with pytest.raises(ValueError, match="same source_event_hash"):
        build_duplicate_evidence_receipt(
            duplicate_evidence,
            parent_source_event_hash=h("source:old"),
            observed_at=260,
        )


def test_valid_independent_evidence_advances_distribution_and_history():
    dist = distribution()
    m = model(dist)
    ev = evidence(dist=dist, m=m)
    posterior, receipt = build_multi_hypothesis_update(
        distribution=dist,
        likelihood_model=m,
        evidence=ev,
        applied_at=260,
        updater_ref="multi-keeper",
    )
    assert posterior.generation == dist.generation + 1
    assert posterior.evidence_state_hash != dist.evidence_state_hash
    assert receipt.posterior_distribution_hash == posterior.distribution_hash
    assert sum(value for _, value in posterior.probability_bps) == 10_000
