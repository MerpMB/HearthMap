"""Plain-text explanation of an assessment ("why does this unit have this score?")."""

from __future__ import annotations

from hearthmap.config.models import ScoringConfig
from hearthmap.scoring.models import Assessment


def render_explanation(assessment: Assessment, config: ScoringConfig | None = None) -> str:
    labels = {d.id: d.label for d in config.dimensions} if config else {}
    a = assessment
    lines = [f"UNIT: {a.unit_id}", f"MODEL: {a.model_id} {a.model_version}", ""]

    lines += ["STATUS", f"  {a.status.value}", ""]

    total = "n/a" if a.suitability_score is None else f"{a.suitability_score:.1f} / 100"
    lines += ["TOTAL", f"  {total}"]
    if a.coverage < 1:
        lines.append(f"  (weight coverage {a.coverage:.0%})")
    lines.append("")

    if a.exclusion_reasons:
        lines.append("EXCLUDED BECAUSE")
        for r in a.exclusion_reasons:
            lines.append(f"  x {r.constraint_id}: {r.reason} [confidence {r.confidence.value}]")
        lines.append("")

    lines.append("COMPONENTS")
    for dim_id, weight in a.weights.items():
        comp = a.components.get(dim_id)
        label = labels.get(dim_id, dim_id)
        if comp is None or comp.value is None:
            value = "missing"
            conf = "-"
        else:
            value = f"{comp.value:.0f}"
            conf = comp.confidence.value
        lines.append(f"  {label:<36} {value:>7}  (w {weight:.0%}, confidence {conf})")
    lines.append("")

    lines += ["CONFIDENCE", f"  {a.confidence.value}", ""]

    why = [r for c in a.components.values() for r in c.reasons]
    if why:
        lines.append("WHY")
        lines += [f"  + {r}" for r in why]
        lines.append("")

    concerns = [c for comp in a.components.values() for c in comp.concerns]
    concerns += [f"{r.constraint_id} not resolved: {r.reason}" for r in a.unresolved_constraints]
    concerns += [f"component missing: {labels.get(d, d)}" for d in a.missing_components]
    concerns += a.notes
    if concerns:
        lines.append("CONCERNS")
        lines += [f"  - {c}" for c in concerns]
        lines.append("")

    lines += ["SOURCES", "  " + (", ".join(a.source_ids) if a.source_ids else "(none recorded)")]
    return "\n".join(lines)
