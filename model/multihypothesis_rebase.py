from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from model.multihypothesis import HypothesisDistribution, MultiLikelihoodModel, make_multi_likelihood_model


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class MultiLikelihoodRebaseReceipt:
    candidate_hash: str
    old_model_hash: str
    new_model_hash: str
    prior_distribution_hash: str
    posterior_distribution_hash: str
    conditioning_evidence_hashes: tuple[str, ...]
    old_model_generation: int
    new_model_generation: int
    rebased_at: int
    rebase_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/multi-likelihood-rebase/v1.11",
            "candidate_hash": self.candidate_hash,
            "old_model_hash": self.old_model_hash,
            "new_model_hash": self.new_model_hash,
            "prior_distribution_hash": self.prior_distribution_hash,
            "posterior_distribution_hash": self.posterior_distribution_hash,
            "conditioning_evidence_hashes": list(self.conditioning_evidence_hashes),
            "old_model_generation": self.old_model_generation,
            "new_model_generation": self.new_model_generation,
            "rebased_at": self.rebased_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("old_model_hash", self.old_model_hash),
            ("new_model_hash", self.new_model_hash),
            ("prior_distribution_hash", self.prior_distribution_hash),
            ("posterior_distribution_hash", self.posterior_distribution_hash),
            ("rebase_hash", self.rebase_hash),
        ):
            _require_digest(name, value)
        for value in self.conditioning_evidence_hashes:
            _require_digest("conditioning_evidence_hash", value)
        if self.new_model_generation != self.old_model_generation + 1:
            raise ValueError("multi likelihood rebase must advance exactly one generation")
        if self.rebased_at < 0:
            raise ValueError("rebased_at must be >= 0")
        if self.rebase_hash != _digest(self.material()):
            raise ValueError("rebase_hash does not match multi likelihood rebase material")


def rebase_multi_likelihood_model(
    model: MultiLikelihoodModel,
    *,
    posterior_distribution: HypothesisDistribution,
    rebased_at: int,
) -> tuple[MultiLikelihoodModel, MultiLikelihoodRebaseReceipt]:
    model.validate()
    posterior_distribution.validate()
    rebased = make_multi_likelihood_model(
        candidate_hash=model.candidate_hash,
        distribution=posterior_distribution,
        positive_likelihood_bps=model.positive_likelihood_bps,
        conditioning_evidence_hashes=model.conditioning_evidence_hashes,
        model_ref=model.model_ref,
        model_generation=model.model_generation + 1,
    )
    fields = {
        "candidate_hash": model.candidate_hash,
        "old_model_hash": model.model_hash,
        "new_model_hash": rebased.model_hash,
        "prior_distribution_hash": model.distribution_hash,
        "posterior_distribution_hash": posterior_distribution.distribution_hash,
        "conditioning_evidence_hashes": model.conditioning_evidence_hashes,
        "old_model_generation": model.model_generation,
        "new_model_generation": rebased.model_generation,
        "rebased_at": rebased_at,
    }
    provisional = MultiLikelihoodRebaseReceipt(**fields, rebase_hash="0" * 64)
    receipt = MultiLikelihoodRebaseReceipt(**fields, rebase_hash=_digest(provisional.material()))
    receipt.validate()
    return rebased, receipt
