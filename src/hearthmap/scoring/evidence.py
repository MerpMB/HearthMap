"""Cross-check hard-constraint evidence against the data-source registry.

A FAIL (definitive exclusion) may only rest on sources that are VERIFIED and
explicitly permitted for POTENTIAL_HARD_EXCLUSION. Screening geometry (for
example an approximate forest-reserve boundary) can only support a FLAG.
"""

from __future__ import annotations

from collections.abc import Iterable

from hearthmap.provenance.registry import DataSourceRegistry, PermittedUse
from hearthmap.scoring.models import ConstraintOutcome, HardConstraintResult


class EvidenceAuthorityError(ValueError):
    """A result claims more authority than its sources permit."""


def check_evidence_authority(
    results: Iterable[HardConstraintResult], registry: DataSourceRegistry
) -> None:
    for r in results:
        if r.outcome is not ConstraintOutcome.FAIL:
            continue
        if not r.source_ids:
            raise EvidenceAuthorityError(f"{r.constraint_id}: FAIL without any source")
        weak = [
            s
            for s in r.source_ids
            if s not in registry or not registry.permits(s, PermittedUse.POTENTIAL_HARD_EXCLUSION)
        ]
        if weak:
            raise EvidenceAuthorityError(
                f"{r.constraint_id}: sources {weak} are not verified for hard exclusion; "
                "report a FLAG instead"
            )
