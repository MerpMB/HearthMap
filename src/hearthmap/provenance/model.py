"""Provenance records for processed artifacts (docs/architecture/overview.md §3.2).

A record answers: which sources (by registry id and version), acquired when, in
which original CRS, transformed how, by which code, with what confidence and
limitations - so "why does this cell have this value?" is a lookup.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from hearthmap.enums import Confidence

SIDECAR_SUFFIX = ".provenance.json"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceReference(_Model):
    """One input dataset as actually used."""

    source_id: str = Field(description="Data-source registry id")
    source_version: str | None = Field(default=None, description="Publisher version/edition")
    source_date: str | None = Field(default=None, description="Date/vintage the data describes")
    acquired_at: datetime | None = None
    original_crs: str | None = None
    local_path: str | None = None
    checksum_sha256: str | None = None
    synthetic: bool = False


class ProcessingStep(_Model):
    """One transformation, in order. ``operation`` is a short verb such as
    ``read``, ``reproject``, ``repair``, ``filter``, ``clip``, ``aggregate``,
    ``calculate``, ``grid``, ``write``."""

    operation: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class TransformationStep(_Model):
    """One PROJ coordinate-operation step (a conversion or a datum transformation)."""

    name: str
    kind: str  # "Conversion" | "Transformation" | ...
    authority_code: str | None = None  # e.g. "EPSG:1812"
    accuracy_m: float | None = None  # stated accuracy; None when not published
    ballpark: bool = False  # True = no real datum shift (PROJ "ballpark" fallback)


class TransformationRecord(_Model):
    """Exactly how coordinates were moved between CRSs (datum contract, ADR-0006).

    Every normalisation must record the source/destination CRS and datum, the
    operation PROJ actually used (with authority codes and stated accuracy),
    and which alternatives existed, so no datum choice is ever silent.
    """

    source_crs: str
    source_datum: str
    target_crs: str
    target_datum: str
    datum_change: bool
    operation: str
    steps: list[TransformationStep]
    transformation_codes: list[str] = Field(default_factory=list)
    accuracy_m: float | None = None
    area_of_use: str | None = None
    candidates: list[str] = Field(default_factory=list)
    selection: Literal["only_candidate", "best_ranked", "pinned"]
    proj_pipeline: str | None = None
    pyproj_version: str
    proj_version: str


class ProvenanceRecord(_Model):
    schema_version: Literal[1] = 1
    artifact_id: str
    artifact_path: str | None = None
    artifact_kind: Literal["vector", "raster", "table", "report"] = "vector"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    code_version: str = "unknown"
    sources: list[SourceReference] = Field(default_factory=list)
    normalized_crs: str | None = None
    steps: list[ProcessingStep] = Field(default_factory=list)
    method: str | None = None
    spatial_resolution: str | None = None
    confidence: Confidence = Confidence.UNKNOWN
    limitations: list[str] = Field(default_factory=list)
    synthetic: bool = False
    crs_transformations: list[TransformationRecord] = Field(default_factory=list)

    def with_step(self, operation: str, description: str, **parameters: Any) -> ProvenanceRecord:
        """Return a copy with one more processing step appended."""
        step = ProcessingStep(operation=operation, description=description, parameters=parameters)
        return self.model_copy(update={"steps": [*self.steps, step]})

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, text: str) -> ProvenanceRecord:
        return cls.model_validate_json(text)

    def write_sidecar(self, artifact_path: Path | str) -> Path:
        path = sidecar_path(artifact_path)
        path.write_text(self.to_json() + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_sidecar(cls, artifact_path: Path | str) -> ProvenanceRecord:
        return cls.from_json(sidecar_path(artifact_path).read_text(encoding="utf-8"))


def sidecar_path(artifact_path: Path | str) -> Path:
    path = Path(artifact_path)
    return path.with_name(path.name + SIDECAR_SUFFIX)


def sha256_file(path: Path | str, *, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def current_code_version(repo_dir: Path | str | None = None) -> str:
    """Git commit of the working tree, suffixed ``-dirty`` if there are local
    changes; ``"unknown"`` when git is unavailable."""
    cwd = str(repo_dir) if repo_dir is not None else None
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha
