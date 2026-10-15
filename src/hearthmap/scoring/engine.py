"""Two-stage scoring engine: hard exclusion, then weighted suitability.

Contract (docs/product/scoring-model-v0.1.md, ADR-0003, ADR-0007):

    any hard constraint FAIL  -> EXCLUDED (definitive), suitability_score = None
    else UNKNOWN + strict     -> EXCLUDED (conservative_policy)
    else any UNKNOWN or FLAG  -> UNRESOLVED
    else                      -> ELIGIBLE

FAIL is only accepted for constraints configured with
``definitive_exclusion_allowed``; screening or approximate legal evidence is a
FLAG and can never become an exclusion. Exclusions are never converted into
negative points. Only complete, eligible scores are rankable unless the
experimental ``allow_incomplete_ranking`` policy is on.
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
    """Inputs reference unknown dimensions/constraints, are duplicated, or claim
    more authority than the constraint permits."""


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
        self._constraints = {c.id: c for c in config.hard_constraints}
        self._enabled_constraints = [c.id for c in config.enabled_constraints]

    # ------------------------------------------------------------ stage A

    def evaluate_constraints(self, results: Iterable[HardConstraintResult]) -> dict[str, object]:
        """Resolve eligibility.

        Returns a dict with ``status``, ``failed``, ``unknown``, ``flags``,
        ``considered`` and ``basis``.
        """
        by_id = _index_unique(results, "constraint_id", "hard-constraint result")
        undefined = sorted(set(by_id) - set(self._constraints))
        if undefined:
            raise ScoringInputError(f"results for undefined hard constraints: {undefined}")
        for r in by_id.values():
            if (
                r.outcome is ConstraintOutcome.FAIL
                and not self._constraints[r.constraint_id].definitive_exclusion_allowed
            ):
                raise ScoringInputError(
                    f"{r.constraint_id} does not permit definitive exclusion; evidence of this "
                    "kind must be reported as FLAG (screening / legal verification)"
                )

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
        flags = [r for r in considered if r.outcome is ConstraintOutcome.FLAG]
        basis = None
        if failed:
            status, basis = EligibilityStatus.EXCLUDED, "definitive"
        elif unknown and self.config.policies.unknown_hard_constraint == "exclude":
            status, basis = EligibilityStatus.EXCLUDED, "conservative_policy"
        elif unknown or flags:
            status = EligibilityStatus.UNRESOLVED
        else:
            status = EligibilityStatus.ELIGIBLE
        return {
            "status": status,
            "failed": failed,
            "unknown": unknown,
            "flags": flags,
            "considered": considered,
            "basis": basis,
        }

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
            "(assumes missing dimensions resemble the others - exploratory only, not rankable)"
        )
        return score, coverage, missing, notes

    # ------------------------------------------------------------ combined

    def assess(
        self,
        unit_id: str,
        constraint_results: Iterable[HardConstraintResult] = (),
        component_scores: Iterable[ComponentScore] = (),
    ) -> Assessment:
        ev = self.evaluate_constraints(constraint_results)
        status: EligibilityStatus = ev["status"]  # type: ignore[assignment]
        failed: list[HardConstraintResult] = ev["failed"]  # type: ignore[assignment]
        unknown: list[HardConstraintResult] = ev["unknown"]  # type: ignore[assignment]
        flags: list[HardConstraintResult] = ev["flags"]  # type: ignore[assignment]
        considered: list[HardConstraintResult] = ev["considered"]  # type: ignore[assignment]
        components = _index_unique(component_scores, "dimension_id", "component score")

        notes: list[str] = []
        if status is EligibilityStatus.EXCLUDED:
            # Components are kept for explanation only; no total is produced.
            score: float | None = None
            missing: list[str] = []
            _, coverage, _, _ = self.weighted_score(components)
            if not failed:
                notes.append(
                    "excluded by conservative policy: unevaluated hard constraints are treated "
                    "as failures (not a definitive finding)"
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
                    "provisional: eligibility unresolved until every hard constraint is evaluated "
                    "and every flag is verified"
                )

        if score is None:
            score_basis = "none"
        elif missing:
            score_basis = "renormalized"
        else:
            score_basis = "complete"

        if self.config.policies.allow_incomplete_ranking:
            rankable = score is not None and status is not EligibilityStatus.EXCLUDED
            if rankable and (score_basis != "complete" or status is not EligibilityStatus.ELIGIBLE):
                notes.append("EXPERIMENTAL ranking mode: incomplete or unresolved score is ranked")
        else:
            rankable = status is EligibilityStatus.ELIGIBLE and score_basis == "complete"

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
            exclusion_basis=ev["basis"],  # type: ignore[arg-type]
            unresolved_constraints=unknown if status is EligibilityStatus.UNRESOLVED else [],
            flags=flags,
            missing_components=missing,
            confidence=confidence,
            notes=notes,
            source_ids=source_ids,
            score_basis=score_basis,
            rankable=rankable,
        )

    # ------------------------------------------------------------ ranking

    def rank(self, assessments: Iterable[Assessment]) -> list[Assessment]:
        """Rankable assessments, best first. Non-rankable units are omitted,
        never mixed in with complete scores."""
        ranked = [a for a in assessments if a.rankable and a.suitability_score is not None]
        return sorted(ranked, key=lambda a: (-a.suitability_score, a.unit_id))  # type: ignore[operator]
