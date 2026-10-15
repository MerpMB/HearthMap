"""Validated configuration models.

Configuration is product *policy* (weights, constraints, grid size, CRS), kept
out of code so it can be tuned without touching logic. Every model forbids
unknown keys so typos fail loudly instead of being silently ignored.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pyproj import CRS
from pyproj.exceptions import CRSError

from hearthmap.enums import VerificationStatus
from hearthmap.spatial.crs import WEB_MERCATOR_EPSG_CODES, is_metric_projected

_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _parse_crs(value: str) -> CRS:
    try:
        return CRS.from_user_input(value)
    except CRSError as exc:
        raise ValueError(f"not a recognised CRS: {value!r} ({exc})") from exc


# --------------------------------------------------------------------- regions


class SanityEnvelope(_StrictModel):
    """Coarse box for catching gross CRS errors. Never used as a boundary."""

    crs: str
    bounds: tuple[float, float, float, float]

    @field_validator("crs")
    @classmethod
    def _crs_parses(cls, v: str) -> str:
        _parse_crs(v)
        return v

    @field_validator("bounds")
    @classmethod
    def _ordered(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        minx, miny, maxx, maxy = v
        if not (minx < maxx and miny < maxy):
            raise ValueError(f"bounds must be [minx, miny, maxx, maxy] with min < max, got {v}")
        return v


class StudyArea(_StrictModel):
    id: str = Field(pattern=_ID_PATTERN)
    name: str
    sanity_envelope: SanityEnvelope


class RegionConfig(_StrictModel):
    id: str = Field(pattern=_ID_PATTERN)
    name_en: str
    name_th: str | None = None
    province_code: str | None = None
    province_code_status: VerificationStatus = VerificationStatus.NEEDS_RESEARCH
    enabled: bool = True


class RegionsConfig(_StrictModel):
    schema_version: Literal[1]
    study_area: StudyArea
    regions: list[RegionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_and_enabled(self) -> RegionsConfig:
        ids = [r.id for r in self.regions]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate region ids: {dupes}")
        if not any(r.enabled for r in self.regions):
            raise ValueError("at least one region must be enabled")
        return self

    @property
    def enabled_regions(self) -> list[RegionConfig]:
        return [r for r in self.regions if r.enabled]


# --------------------------------------------------------------------- spatial


class CRSConfig(_StrictModel):
    canonical: str
    interchange: str
    display: str
    require_explicit_source_crs: bool = True

    @field_validator("canonical")
    @classmethod
    def _canonical_is_metric(cls, v: str) -> str:
        crs = _parse_crs(v)
        if not is_metric_projected(crs):
            raise ValueError(
                f"canonical CRS {v!r} must be a projected CRS in metres; "
                "distance/area work in degrees is not allowed"
            )
        if crs.to_epsg() in WEB_MERCATOR_EPSG_CODES:
            raise ValueError(
                f"canonical CRS {v!r} is Web Mercator, which distorts distance and area; "
                "use it only as the display CRS"
            )
        return v

    @field_validator("interchange")
    @classmethod
    def _interchange_is_geographic(cls, v: str) -> str:
        if not _parse_crs(v).is_geographic:
            raise ValueError(f"interchange CRS {v!r} should be geographic (e.g. EPSG:4326)")
        return v

    @field_validator("display")
    @classmethod
    def _display_parses(cls, v: str) -> str:
        _parse_crs(v)
        return v


class GridConfig(_StrictModel):
    cell_size_m: float = Field(gt=0, le=50_000)
    selection: Literal["intersects", "centroid_within"] = "intersects"
    id_prefix: str = Field(default="G", pattern=r"^[A-Z][A-Z0-9]*$")
    max_cells: int = Field(default=2_000_000, gt=0)


class SpatialConfig(_StrictModel):
    schema_version: Literal[1]
    crs: CRSConfig
    grid: GridConfig


# --------------------------------------------------------------------- scoring


class DimensionConfig(_StrictModel):
    id: str = Field(pattern=_ID_PATTERN)
    label: str
    weight: float = Field(ge=0)
    description: str | None = None

    @field_validator("weight")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("weight must be finite")
        return v


class HardConstraintConfig(_StrictModel):
    id: str = Field(pattern=_ID_PATTERN)
    label: str
    description: str
    enabled: bool = True
    # False until a concrete, data-backed threshold has been agreed.
    rule_defined: bool = False


class ScoringPolicies(_StrictModel):
    unknown_hard_constraint: Literal["unresolved", "exclude"] = "unresolved"
    missing_component: Literal["null_total", "renormalize"] = "null_total"
    min_component_coverage: float = Field(default=0.75, gt=0, le=1)


class ScoringConfig(_StrictModel):
    schema_version: Literal[1]
    model_id: str
    model_version: str
    status: Literal["PROVISIONAL", "ACCEPTED"]
    weights_total: float | None = Field(default=None, gt=0)
    dimensions: list[DimensionConfig] = Field(min_length=1)
    policies: ScoringPolicies = ScoringPolicies()
    hard_constraints: list[HardConstraintConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_weights_and_ids(self) -> ScoringConfig:
        dim_ids = [d.id for d in self.dimensions]
        dupes = sorted({i for i in dim_ids if dim_ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate dimension ids: {dupes}")

        hc_ids = [c.id for c in self.hard_constraints]
        dupes = sorted({i for i in hc_ids if hc_ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate hard-constraint ids: {dupes}")

        total = sum(d.weight for d in self.dimensions)
        if total <= 0:
            raise ValueError("at least one dimension must have a positive weight")
        if self.weights_total is not None and not math.isclose(
            total, self.weights_total, rel_tol=0, abs_tol=1e-6
        ):
            raise ValueError(
                f"dimension weights sum to {total:g}, expected weights_total={self.weights_total:g}"
            )
        return self

    @property
    def dimension_ids(self) -> list[str]:
        return [d.id for d in self.dimensions]

    @property
    def enabled_constraints(self) -> list[HardConstraintConfig]:
        return [c for c in self.hard_constraints if c.enabled]

    def normalized_weights(self) -> dict[str, float]:
        """Weights rescaled to sum to 1, in configured order."""
        total = sum(d.weight for d in self.dimensions)
        return {d.id: d.weight / total for d in self.dimensions}
