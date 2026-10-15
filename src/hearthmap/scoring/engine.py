"""Two-stage scoring engine: hard exclusion, then weighted suitability.

Contract (docs/product/scoring-model-v0.1.md, ADR-0003):

    any hard constraint FAIL  -> EXCLUDED, suitability_score = None
    else any UNKNOWN          -> UNRESOLVED (or EXCLUDED under strict policy)
    else                      -> ELIGIBLE

Exclusions are never converted into negative points. The engine does not
compute components from geography; callers supply already-normalised scores.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from hearthmap.config.models import ScoringConfig
from hearthmap.enums import Confidence
from hearthmap.scoring.models import (
    Assessment,
    ComponentScore,
    ConstraintOutcome,
    EligibilityStatus,
    HardConstraintResult,
)


class ScoringInputError(ValueError):
    """Inputs reference unknown dimensions/constraints or are duplicated."""


def _index_unique[T](items: Iterable[T], key: str, kind: str) -> dict[str, T]:
    out: dict[str, T] = {}
    for item in items:
        k = getattr(item, key)
        if k in out:
            raise ScoringInputError(f"duplicate {kind} {k!r}")
        out[k] = item
    return out


class ScoringModel:
    """Applies a :class:`ScoringConfig` to per-unit evidence."""

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config
        self.weights: dict[str, float] = config.normalized_weights()
        self._constraint_ids = {c.id for c in config.hard_constraints}
        self._enabled_constraints = [c.id for c in config.enabled_constraints]

    # ------------------------------------------------------------ stage A

    def evaluate_constraints(
        self, results: Iterable[HardConstraintResult]
    ) -> tuple[
        EligibilityStatus,
        list[HardConstraintResult],
        list[HardConstraintResult],
        list[HardConstraintResult],
    ]:
        """Resolve eligibility. Returns (status, failed, unknown, all_considered)."""
        by_id = _index_unique(results, "constraint_id", "hard-constraint result")
        unknown_ids = sorted(set(by_id) - self._constraint_ids)
        if unknown_ids:
            raise ScoringInputError(f"results for undefined hard constraints: {unknown_ids}")

        considered: list[HardConstraintResult] = []
        for cid in self._enabled_constraints:
            considered.append(
                by_id.get(cid)
                or HardConstraintResult(
                    constraint_id=cid,
                    outcome=ConstraintOutcome.UNKNOWN,
                    reason="not evaluated (no data or rule supplied)",
                )
            )

        failed = [r for r in considered if r.outcome is ConstraintOutcome.FAIL]
        unknown = [r for r in considered if r.outcome is ConstraintOutcome.UNKNOWN]
        if failed or (unknown and self.config.policies.unknown_hard_constraint == "exclude"):
            status = EligibilityStatus.EXCLUDED
        elif unknown:
            status = EligibilityStatus.UNRESOLVED
        else:
            status = EligibilityStatus.ELIGIBLE
        return status, failed, unknown, considered

    # ------------------------------------------------------------ stage B

    def weighted_score(
        self, components: Mapping[str, ComponentScore]
    ) -> tuple[float | None, float, list[str], list[str]]:
        """Weighted suitability. Returns (score, coverage, missing_ids, notes)."""
        unknown_dims = sorted(set(components) - set(self.weights))
        if unknown_dims:
            raise ScoringInputError(f"component scores for undefined dimensions: {unknown_dims}")

        active = {d: w for d, w in self.weights.items() if w > 0}
        available = {
            d: w for d, w in active.items() if d in components and components[d].value is not None
        }
        missing = [d for d in active if d not in available]
        coverage = sum(available.values())
        notes: list[str] = []

        if not missing:
            score = sum(w * components[d].value for d, w in available.items())  # type: ignore[operator]
            return score, coverage, missing, notes

        policy = self.config.policies
        if policy.missing_component == "null_total":
            notes.append(f"score withheld: missing components {missing} (policy null_total)")
            return None, coverage, missing, notes

        if coverage < policy.min_component_coverage or coverage == 0:
            notes.append(
                f"score withheld: coverage {coverage:.0%} below minimum "
                f"{policy.min_component_coverage:.0%}; missing {missing}"
            )
            return None, coverage, missing, notes

        score = sum(w * components[d].value for d, w in available.items()) / coverage  # type: ignore[operator]
        notes.append(
            f"score renormalised over {coverage:.0%} of weight; missing {missing} "
            "(assumes missing dimensions resemble the others - exploratory only)"
        )
        return score, coverage, missing, notes

    # ------------------------------------------------------------ combined

    def assess(
        self,
        unit_id: str,
        constraint_results: Iterable[HardConstraintResult] = (),
        component_scores: Iterable[ComponentScore] = (),
    ) -> Assessment:
        status, failed, unknown, considered = self.evaluate_constraints(constraint_results)
        components = _index_unique(component_scores, "dimension_id", "component score")

        notes: list[str] = []
        if status is EligibilityStatus.EXCLUDED:
            # Components are kept for explanation only; no total is produced.
            score: float | None = None
            missing: list[str] = []
            _, coverage, _, _ = self.weighted_score(components)
            if not failed:
                notes.append(
                    "excluded because unevaluated hard constraints are treated as failures"
                )
            confidence = Confidence.weakest(r.confidence for r in (failed or unknown))
        else:
            score, coverage, missing, notes = self.weighted_score(components)
            contributing = [
                c.confidence
                for d, c in components.items()
                if self.weights.get(d, 0) > 0 and c.value is not None
            ]
            confidence = Confidence.weakest([*contributing, *(r.confidence for r in considered)])
            if status is EligibilityStatus.UNRESOLVED:
                notes.append(
                    "provisional: eligibility unresolved until every hard constraint is evaluated"
                )

        source_ids = sorted(
            {s for c in components.values() for s in c.source_ids}
            | {s for r in considered for s in r.source_ids}
        )
        return Assessment(
            unit_id=unit_id,
            model_id=self.config.model_id,
            model_version=self.config.model_version,
            status=status,
            suitability_score=score,
            components=components,
            weights=self.weights,
            coverage=coverage,
            exclusion_reasons=failed or (unknown if status is EligibilityStatus.EXCLUDED else []),
            unresolved_constraints=unknown if status is EligibilityStatus.UNRESOLVED else [],
            missing_components=missing,
            confidence=confidence,
            notes=notes,
            source_ids=source_ids,
        )
