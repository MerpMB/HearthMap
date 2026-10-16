"""Human visual QA sign-off record (``config/human-qa.yaml``).

A gate is PASSED only with a review date, reviewer role and the reviewer's
reported result; a PENDING gate carries none of them. Nothing here is inferred.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

GateStatus = Literal["PENDING", "PASSED"]


class SignoffRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: GateStatus
    review_date: date | None = None
    reviewer_role: str | None = None
    result: str | None = None
    reviewed_material: str
    # optional review record details (M2D signoff): what was observed, what is NOT resolved, backlog items and notes  # noqa: E501
    observations_reported: tuple[str, ...] = ()
    known_non_blocking_limitations_not_resolved: tuple[str, ...] = ()
    family_scoring: str | None = None
    visualization_backlog: tuple[dict[str, str], ...] = ()
    note: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> SignoffRecord:
        filled = [self.review_date, self.reviewer_role, self.result]
        if self.status == "PASSED" and any(v in (None, "") for v in filled):
            raise ValueError("a PASSED gate needs review_date, reviewer_role and result")
        if self.status == "PENDING" and any(v is not None for v in filled):
            raise ValueError("a PENDING gate cannot carry review details")
        return self


class HumanQA(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    gates: dict[str, SignoffRecord]

    def status(self, gate: str) -> GateStatus:
        return self.gates[gate].status


def load_human_qa(path: Path | str = "config/human-qa.yaml") -> HumanQA:
    return HumanQA.model_validate(yaml.safe_load(Path(path).read_text("utf-8")))
