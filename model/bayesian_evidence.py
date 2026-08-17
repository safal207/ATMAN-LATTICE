from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.active_verification import (
    HypothesisState,
    VerificationLikelihoodModel,
    make_hypothesis_state,
    make_likelihood_model,
)

EvidenceOutcome = Literal["POSITIVE", "NEGATIVE", "INCONCLUSIVE"]
CompletionDecision = Literal["PASS", "HOLD", "FAIL"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _round_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be > 0")
    return (numerator + denominator // 2) // denominator


@dataclass(frozen=True)
class EvidenceInterpretationRule:
    candidate_hash: str
    likelihood_model_hash: str
    pass_outcome: EvidenceOutcome
    hold_outcome: EvidenceOutcome
    fail_outcome: EvidenceOutcome
    rule_ref: str
    rule_generation: int
    registered_at: int
    rule_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/evidence-interpretation-rule/v1.10",
            "candidate_hash": self.candidate_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "pass_outcome": self.pass_outcome,
            "hold_outcome": self.hold_outcome,
            "fail_outcome": self.fail_outcome,
            "rule_ref": self.rule_ref,
            "rule_generation": self.rule_generation,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        _require_digest("candidate_hash", self.candidate_hash)
        _require_digest("likelihood_model_hash", self.likelihood_model_hash)
        _require_digest("rule_hash", self.rule_hash)
        allowed = {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}
        if self.pass_outcome not in allowed or self.hold_outcome not in allowed or self.fail_outcome not in allowed:
            raise ValueError("invalid evidence outcome mapping")
        if not self.rule_ref or self.rule_generation < 0 or self.registered_at < 0:
            raise ValueError("invalid interpretation rule metadata")
        if self.rule_hash != _digest(self.material()):
            raise ValueError("rule_hash does not match rule material")


def make_interpretation_rule(
    *,
    candidate_hash: str,
    likelihood_model_hash: str,
    pass_outcome: EvidenceOutcome,
    hold_outcome: EvidenceOutcome,
    fail_outcome: EvidenceOutcome,
    rule_ref: str,
    rule_generation: int,
    registered_at: int,
) -> EvidenceInterpretationRule:
    fields = {
        "candidate_hash": candidate_hash,
        "likelihood_model_hash": likelihood_model_hash,
        "pass_outcome": pass_outcome,
        "hold_outcome": hold_outcome,
        "fail_outcome": fail_outcome,
        "rule_ref": rule_ref,
        "rule_generation": rule_generation,
        "registered_at": registered_at,
    }
    provisional = EvidenceInterpretationRule(**fields, rule_hash="0" * 64)
    result = EvidenceInterpretationRule(**fields, rule_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class EvidenceInterpretationReceipt:
    candidate_hash: str
    work_hash: str
    completion_hash: str
    completion_decision: CompletionDecision
    prior_hypothesis_hash: str
    likelihood_model_hash: str
    rule_hash: str
    outcome: EvidenceOutcome
    interpreted_at: int
    interpretation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/evidence-interpretation/v1.10",
            "candidate_hash": self.candidate_hash,
            "work_hash": self.work_hash,
            "completion_hash": self.completion_hash,
            "completion_decision": self.completion_decision,
            "prior_hypothesis_hash": self.prior_hypothesis_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "rule_hash": self.rule_hash,
            "outcome": self.outcome,
            "interpreted_at": self.interpreted_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("work_hash", self.work_hash),
            ("completion_hash", self.completion_hash),
            ("prior_hypothesis_hash", self.prior_hypothesis_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("rule_hash", self.rule_hash),
            ("interpretation_hash", self.interpretation_hash),
        ):
            _require_digest(name, value)
        if self.completion_decision not in {"PASS", "HOLD", "FAIL"}:
            raise ValueError("invalid completion decision")
        if self.outcome not in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}:
            raise ValueError("invalid evidence outcome")
        if self.interpreted_at < 0:
            raise ValueError("interpreted_at must be >= 0")
        if self.interpretation_hash != _digest(self.material()):
            raise ValueError("interpretation_hash does not match interpretation material")


def interpret_completion(
    *,
    candidate_hash: str,
    work_hash: str,
    completion_hash: str,
    completion_decision: CompletionDecision,
    prior_hypothesis: HypothesisState,
    likelihood_model: VerificationLikelihoodModel,
    rule: EvidenceInterpretationRule,
    completion_completed_at: int,
    interpreted_at: int,
) -> EvidenceInterpretationReceipt:
    prior_hypothesis.validate()
    likelihood_model.validate()
    rule.validate()
    if rule.candidate_hash != candidate_hash:
        raise ValueError("interpretation rule candidate mismatch")
    if likelihood_model.candidate_hash != candidate_hash:
        raise ValueError("likelihood candidate mismatch")
    if likelihood_model.hypothesis_hash != prior_hypothesis.hypothesis_hash:
        raise ValueError("likelihood/prior mismatch")
    if rule.likelihood_model_hash != likelihood_model.model_hash:
        raise ValueError("interpretation rule likelihood mismatch")
    if rule.registered_at > completion_completed_at:
        raise ValueError("interpretation rule must be precommitted before completion")
    if interpreted_at < completion_completed_at:
        raise ValueError("interpretation cannot precede completion")
    mapping = {
        "PASS": rule.pass_outcome,
        "HOLD": rule.hold_outcome,
        "FAIL": rule.fail_outcome,
    }
    fields = {
        "candidate_hash": candidate_hash,
        "work_hash": work_hash,
        "completion_hash": completion_hash,
        "completion_decision": completion_decision,
        "prior_hypothesis_hash": prior_hypothesis.hypothesis_hash,
        "likelihood_model_hash": likelihood_model.model_hash,
        "rule_hash": rule.rule_hash,
        "outcome": mapping[completion_decision],
        "interpreted_at": interpreted_at,
    }
    provisional = EvidenceInterpretationReceipt(**fields, interpretation_hash="0" * 64)
    result = EvidenceInterpretationReceipt(**fields, interpretation_hash=_digest(provisional.material()))
    result.validate()
    return result


def posterior_probability_bps(
    prior_probability_bps: int,
    likelihood_model: VerificationLikelihoodModel,
    outcome: EvidenceOutcome,
) -> int:
    likelihood_model.validate()
    if prior_probability_bps < 0 or prior_probability_bps > 10_000:
        raise ValueError("prior probability must be 0..10000")
    if outcome == "INCONCLUSIVE":
        return prior_probability_bps
    p = prior_probability_bps
    q = 10_000 - p
    sensitivity = likelihood_model.positive_if_true_bps
    false_positive = likelihood_model.positive_if_false_bps
    if outcome == "POSITIVE":
        true_weight = p * sensitivity
        false_weight = q * false_positive
    elif outcome == "NEGATIVE":
        true_weight = p * (10_000 - sensitivity)
        false_weight = q * (10_000 - false_positive)
    else:
        raise ValueError("invalid evidence outcome")
    denominator = true_weight + false_weight
    if denominator == 0:
        raise ValueError("impossible observation under likelihood model")
    return min(10_000, max(0, _round_ratio(10_000 * true_weight, denominator)))


@dataclass(frozen=True)
class BayesianUpdateReceipt:
    candidate_hash: str
    prior_hypothesis_hash: str
    posterior_hypothesis_hash: str
    interpretation_hash: str
    likelihood_model_hash: str
    prior_probability_bps: int
    posterior_probability_bps: int
    prior_generation: int
    posterior_generation: int
    evidence_state_hash: str
    applied_at: int
    updater_ref: str
    update_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/bayesian-update/v1.10",
            "candidate_hash": self.candidate_hash,
            "prior_hypothesis_hash": self.prior_hypothesis_hash,
            "posterior_hypothesis_hash": self.posterior_hypothesis_hash,
            "interpretation_hash": self.interpretation_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "prior_probability_bps": self.prior_probability_bps,
            "posterior_probability_bps": self.posterior_probability_bps,
            "prior_generation": self.prior_generation,
            "posterior_generation": self.posterior_generation,
            "evidence_state_hash": self.evidence_state_hash,
            "applied_at": self.applied_at,
            "updater_ref": self.updater_ref,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("prior_hypothesis_hash", self.prior_hypothesis_hash),
            ("posterior_hypothesis_hash", self.posterior_hypothesis_hash),
            ("interpretation_hash", self.interpretation_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("evidence_state_hash", self.evidence_state_hash),
            ("update_hash", self.update_hash),
        ):
            _require_digest(name, value)
        if not self.updater_ref or self.applied_at < 0:
            raise ValueError("invalid update metadata")
        if min(self.prior_probability_bps, self.posterior_probability_bps) < 0 or max(self.prior_probability_bps, self.posterior_probability_bps) > 10_000:
            raise ValueError("probabilities must be 0..10000")
        if self.posterior_generation != self.prior_generation + 1:
            raise ValueError("posterior generation must advance exactly once")
        if self.update_hash != _digest(self.material()):
            raise ValueError("update_hash does not match update material")


@dataclass(frozen=True)
class LikelihoodRebaseReceipt:
    candidate_hash: str
    old_model_hash: str
    new_model_hash: str
    prior_hypothesis_hash: str
    posterior_hypothesis_hash: str
    old_model_generation: int
    new_model_generation: int
    rebased_at: int
    rebase_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/likelihood-rebase/v1.10",
            "candidate_hash": self.candidate_hash,
            "old_model_hash": self.old_model_hash,
            "new_model_hash": self.new_model_hash,
            "prior_hypothesis_hash": self.prior_hypothesis_hash,
            "posterior_hypothesis_hash": self.posterior_hypothesis_hash,
            "old_model_generation": self.old_model_generation,
            "new_model_generation": self.new_model_generation,
            "rebased_at": self.rebased_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("old_model_hash", self.old_model_hash),
            ("new_model_hash", self.new_model_hash),
            ("prior_hypothesis_hash", self.prior_hypothesis_hash),
            ("posterior_hypothesis_hash", self.posterior_hypothesis_hash),
            ("rebase_hash", self.rebase_hash),
        ):
            _require_digest(name, value)
        if self.new_model_generation != self.old_model_generation + 1 or self.rebased_at < 0:
            raise ValueError("invalid likelihood rebase generation")
        if self.rebase_hash != _digest(self.material()):
            raise ValueError("rebase_hash does not match rebase material")


def build_bayesian_update(
    *,
    candidate_hash: str,
    prior_hypothesis: HypothesisState,
    likelihood_model: VerificationLikelihoodModel,
    interpretation: EvidenceInterpretationReceipt,
    applied_at: int,
    updater_ref: str,
) -> tuple[HypothesisState, BayesianUpdateReceipt]:
    prior_hypothesis.validate()
    likelihood_model.validate()
    interpretation.validate()
    if interpretation.candidate_hash != candidate_hash:
        raise ValueError("interpretation candidate mismatch")
    if interpretation.prior_hypothesis_hash != prior_hypothesis.hypothesis_hash:
        raise ValueError("interpretation prior mismatch")
    if interpretation.likelihood_model_hash != likelihood_model.model_hash:
        raise ValueError("interpretation likelihood mismatch")
    posterior_probability = posterior_probability_bps(
        prior_hypothesis.true_probability_bps,
        likelihood_model,
        interpretation.outcome,
    )
    evidence_state_hash = _digest({
        "domain": "ATMAN-LATTICE/evidence-state/v1.10",
        "prior_evidence_state_hash": prior_hypothesis.evidence_state_hash,
        "completion_hash": interpretation.completion_hash,
        "interpretation_hash": interpretation.interpretation_hash,
        "likelihood_model_hash": likelihood_model.model_hash,
        "outcome": interpretation.outcome,
    })
    posterior = make_hypothesis_state(
        prior_hypothesis.hypothesis_ref,
        subject_identity_ref=prior_hypothesis.subject_identity_ref,
        true_probability_bps=posterior_probability,
        evidence_state_hash=evidence_state_hash,
        generation=prior_hypothesis.generation + 1,
    )
    fields = {
        "candidate_hash": candidate_hash,
        "prior_hypothesis_hash": prior_hypothesis.hypothesis_hash,
        "posterior_hypothesis_hash": posterior.hypothesis_hash,
        "interpretation_hash": interpretation.interpretation_hash,
        "likelihood_model_hash": likelihood_model.model_hash,
        "prior_probability_bps": prior_hypothesis.true_probability_bps,
        "posterior_probability_bps": posterior_probability,
        "prior_generation": prior_hypothesis.generation,
        "posterior_generation": posterior.generation,
        "evidence_state_hash": evidence_state_hash,
        "applied_at": applied_at,
        "updater_ref": updater_ref,
    }
    provisional = BayesianUpdateReceipt(**fields, update_hash="0" * 64)
    receipt = BayesianUpdateReceipt(**fields, update_hash=_digest(provisional.material()))
    receipt.validate()
    return posterior, receipt


def rebase_likelihood_model(
    model: VerificationLikelihoodModel,
    *,
    posterior_hypothesis: HypothesisState,
    rebased_at: int,
) -> tuple[VerificationLikelihoodModel, LikelihoodRebaseReceipt]:
    model.validate()
    posterior_hypothesis.validate()
    old_hypothesis_hash = model.hypothesis_hash
    rebased = make_likelihood_model(
        candidate_hash=model.candidate_hash,
        hypothesis_hash=posterior_hypothesis.hypothesis_hash,
        positive_if_true_bps=model.positive_if_true_bps,
        positive_if_false_bps=model.positive_if_false_bps,
        model_ref=model.model_ref,
        model_generation=model.model_generation + 1,
    )
    fields = {
        "candidate_hash": model.candidate_hash,
        "old_model_hash": model.model_hash,
        "new_model_hash": rebased.model_hash,
        "prior_hypothesis_hash": old_hypothesis_hash,
        "posterior_hypothesis_hash": posterior_hypothesis.hypothesis_hash,
        "old_model_generation": model.model_generation,
        "new_model_generation": rebased.model_generation,
        "rebased_at": rebased_at,
    }
    provisional = LikelihoodRebaseReceipt(**fields, rebase_hash="0" * 64)
    receipt = LikelihoodRebaseReceipt(**fields, rebase_hash=_digest(provisional.material()))
    receipt.validate()
    return rebased, receipt
