"""Human spatial-QA helpers (M1A.1).

Everything here is DESCRIPTIVE. Review layers produced with these helpers are
marked ``review_only`` and are refused as inputs to overlays and scoring.
"""

from hearthmap.qa.boundary import disagreement_zones, uncertainty_cells
from hearthmap.qa.coverage import CoverageAccounting, coverage_accounting
from hearthmap.qa.distribution import threshold_distribution
from hearthmap.qa.overlaps import category_area_combinations, category_cell_combinations
from hearthmap.qa.repair import RepairAuditRecord, audit_repairs
from hearthmap.qa.review import (
    REVIEW_SOURCE_PREFIX,
    ReviewLayerError,
    assert_not_review_layer,
    is_review_layer,
    mark_review_only,
)

__all__ = [
    "REVIEW_SOURCE_PREFIX",
    "CoverageAccounting",
    "RepairAuditRecord",
    "ReviewLayerError",
    "assert_not_review_layer",
    "audit_repairs",
    "category_area_combinations",
    "category_cell_combinations",
    "coverage_accounting",
    "disagreement_zones",
    "is_review_layer",
    "mark_review_only",
    "threshold_distribution",
    "uncertainty_cells",
]
