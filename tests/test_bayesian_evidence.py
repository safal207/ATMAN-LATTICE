from dataclasses import replace

import pytest

from model.active_verification import make_hypothesis_state, make_likelihood_model
from model.bayesian_evidence import (
    build_bayesian_update,
    interpret_completion,
    make_interpretation_rule,
    posterior_probability_bps,
    rebase_likelihood_model,
)

CANDIDATE = "a" * 64
WORK = "b" * 64
COMPLETION = "c" * 64
EVIDENCE = "d" * 64


def fixture(*, probability=5000, sensitivity=9000, false_positive=1000, registered_at=100):
    prior = make_hypothesis_state(
        "hypothesis:coherent-path",
        subject_identity_ref="agent:bayes",
        true_probability_bps=probability,
        evidence_state_hash=EVIDENCE,
        generation=3,
    )
    model = make_likelihood_model(
        candidate_hash=CANDIDATE,
        hypothesis_hash=prior.hypothesis_hash,
        positive_if_true_bps=sensitivity,
        positive_if_false_bps=false_positive,
        model_ref="likelihood:geometry",
        model_generation=7,
    )
    rule = make_interpretation_rule(
        candidate_hash=CANDIDATE,
        likelihood_model_hash=model.model_hash,
        pass_outcome="POSITIVE",
        hold_outcome="INCONCLUSIVE",
        fail_outcome="NEGATIVE",
        rule_ref="rule:geometry",
        rule_generation=2,
        registered_at=registered_at,
    )
    return prior, model, rule


def interpretation(decision="PASS", *, completed_at=200, interpreted_at=210):
    prior, model, rule = fixture()
    receipt = interpret_completion(
        candidate_hash=CANDIDATE,
        work_hash=WORK,
        completion_hash=COMPLETION,
        completion_decision=decision,
        prior_hypothesis=prior,
        likelihood_model=model,
        rule=rule,
        completion_completed_at=completed_at,
        interpreted_at=interpreted_at,
    )
    return prior, model, rule, receipt


def test_positive_evidence_moves_balanced_prior_to_ninety_percent():
    prior, model, _, receipt = interpretation("PASS")
    posterior, update = build_bayesian_update(
        candidate_hash=CANDIDATE,
        prior_hypothesis=prior,
        likelihood_model=model,
        interpretation=receipt,
        applied_at=220,
        updater_ref="bayes-keeper",
    )
    assert posterior.true_probability_bps == 9000
    assert posterior.generation == prior.generation + 1
    assert posterior.evidence_state_hash != prior.evidence_state_hash
    assert update.posterior_hypothesis_hash == posterior.hypothesis_hash


def test_negative_evidence_moves_balanced_prior_to_ten_percent():
    prior, model, _, receipt = interpretation("FAIL")
    posterior, _ = build_bayesian_update(
        candidate_hash=CANDIDATE,
        prior_hypothesis=prior,
        likelihood_model=model,
        interpretation=receipt,
        applied_at=220,
        updater_ref="bayes-keeper",
    )
    assert posterior.true_probability_bps == 1000


def test_inconclusive_evidence_preserves_probability_but_advances_evidence_state():
    prior, model, _, receipt = interpretation("HOLD")
    posterior, update = build_bayesian_update(
        candidate_hash=CANDIDATE,
        prior_hypothesis=prior,
        likelihood_model=model,
        interpretation=receipt,
        applied_at=220,
        updater_ref="bayes-keeper",
    )
    assert posterior.true_probability_bps == prior.true_probability_bps
    assert posterior.generation == prior.generation + 1
    assert posterior.evidence_state_hash != prior.evidence_state_hash
    assert update.posterior_generation == update.prior_generation + 1


def test_interpretation_rule_must_be_precommitted_before_completion():
    prior, model, rule = fixture(registered_at=201)
    with pytest.raises(ValueError, match="precommitted"):
        interpret_completion(
            candidate_hash=CANDIDATE,
            work_hash=WORK,
            completion_hash=COMPLETION,
            completion_decision="PASS",
            prior_hypothesis=prior,
            likelihood_model=model,
            rule=rule,
            completion_completed_at=200,
            interpreted_at=210,
        )


def test_rule_is_bound_to_exact_likelihood_model():
    prior, model, rule = fixture()
    other = make_likelihood_model(
        candidate_hash=CANDIDATE,
        hypothesis_hash=prior.hypothesis_hash,
        positive_if_true_bps=8000,
        positive_if_false_bps=2000,
        model_ref="likelihood:other",
        model_generation=8,
    )
    with pytest.raises(ValueError, match="rule likelihood mismatch"):
        interpret_completion(
            candidate_hash=CANDIDATE,
            work_hash=WORK,
            completion_hash=COMPLETION,
            completion_decision="PASS",
            prior_hypothesis=prior,
            likelihood_model=other,
            rule=rule,
            completion_completed_at=200,
            interpreted_at=210,
        )


def test_impossible_observation_under_model_is_rejected():
    prior, model, _ = fixture(probability=10000, sensitivity=0, false_positive=0)
    with pytest.raises(ValueError, match="impossible observation"):
        posterior_probability_bps(prior.true_probability_bps, model, "POSITIVE")


def test_likelihood_rebase_preserves_conditional_characteristics():
    prior, model, _, receipt = interpretation("PASS")
    posterior, _ = build_bayesian_update(
        candidate_hash=CANDIDATE,
        prior_hypothesis=prior,
        likelihood_model=model,
        interpretation=receipt,
        applied_at=220,
        updater_ref="bayes-keeper",
    )
    rebased, rebase = rebase_likelihood_model(model, posterior_hypothesis=posterior, rebased_at=220)
    assert rebased.hypothesis_hash == posterior.hypothesis_hash
    assert rebased.positive_if_true_bps == model.positive_if_true_bps
    assert rebased.positive_if_false_bps == model.positive_if_false_bps
    assert rebased.model_generation == model.model_generation + 1
    assert rebase.old_model_hash == model.model_hash
    assert rebase.new_model_hash == rebased.model_hash


def test_self_consistent_update_cannot_be_rebound_to_another_interpretation():
    prior, model, _, receipt = interpretation("PASS")
    posterior, update = build_bayesian_update(
        candidate_hash=CANDIDATE,
        prior_hypothesis=prior,
        likelihood_model=model,
        interpretation=receipt,
        applied_at=220,
        updater_ref="bayes-keeper",
    )
    forged = replace(update, interpretation_hash="e" * 64)
    with pytest.raises(ValueError, match="update_hash"):
        forged.validate()
    assert posterior.true_probability_bps == 9000
