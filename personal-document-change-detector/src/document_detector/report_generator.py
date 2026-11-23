"""Render a validated comparison as Markdown or JSON."""

from __future__ import annotations

import json

from document_detector.config import IMPORTANCE_RANK
from document_detector.schemas import (
    CATEGORY_LABELS,
    IMPORTANCE_LABELS,
    ChangeRecord,
    ComparisonReport,
    ComparisonSummary,
)


def build_summary(changes: list[ChangeRecord]) -> ComparisonSummary:
    counts = {
        "added": 0,
        "removed": 0,
        "modified": 0,
        "moved": 0,
        "formatting_only": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "informational": 0,
    }
    for change in changes:
        if change.change_type in counts:
            counts[change.change_type] += 1
        counts[change.importance] += 1
        if change.formatting_only:
            counts["formatting_only"] += 1
    return ComparisonSummary(
        total_changes=len(changes),
        added=counts["added"],
        removed=counts["removed"],
        modified=counts["modified"],
        moved=counts["moved"],
        formatting_only=counts["formatting_only"],
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        informational=counts["informational"],
    )


def build_recommendations(changes: list[ChangeRecord]) -> list[str]:
    prioritized = sorted(
        [c for c in changes if not c.formatting_only and c.importance in {"critical", "high", "medium"}],
        key=lambda c: (-IMPORTANCE_RANK[c.importance], c.change_id),
    )
    recommendations: list[str] = []
    for change in prioritized[:8]:
        recommendations.append(change.recommendation)
    if not recommendations and changes:
        recommendations.append("No high-priority changes were detected. Spot-check the remaining differences.")
    return recommendations


def render_json(report: ComparisonReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)


def render_markdown(report: ComparisonReport) -> str:
    summary = report.summary
    previous = report.documents.get("previous")
    updated = report.documents.get("updated")
    lines = [
        "# Document comparison summary",
        "",
        f"**{summary.total_changes} changes detected**",
        "",
        f"- Previous: `{previous.filename if previous else 'unknown'}`",
        f"- Updated: `{updated.filename if updated else 'unknown'}`",
        f"- Provider: `{report.provider}`",
        "",
        "## Statistics",
        "",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Added | {summary.added} |",
        f"| Removed | {summary.removed} |",
        f"| Modified | {summary.modified} |",
        f"| Moved | {summary.moved} |",
        f"| Formatting only | {summary.formatting_only} |",
        f"| Critical | {summary.critical} |",
        f"| High | {summary.high} |",
        f"| Medium | {summary.medium} |",
        f"| Low | {summary.low} |",
        f"| Informational | {summary.informational} |",
        "",
    ]

    ranked = sorted(
        report.changes,
        key=lambda c: (-IMPORTANCE_RANK[c.importance], c.change_id),
    )
    if ranked:
        lines.extend(
            [
                "## Change overview",
                "",
                "| ID | Section | Previous | Updated | Importance |",
                "|---|---|---|---|---|",
            ]
        )
        for change in ranked:
            prev = _cell(change.previous_text)
            upd = _cell(change.updated_text)
            lines.append(
                f"| {change.change_id} | {_cell(change.section)} | {prev} | {upd} | "
                f"{IMPORTANCE_LABELS[change.importance]} |"
            )
        lines.append("")

    lines.extend(["## Detailed change analysis", ""])
    if not ranked:
        lines.append("No differences were detected after normalization.")
        lines.append("")
    for index, change in enumerate(ranked, start=1):
        categories = ", ".join(CATEGORY_LABELS.get(c, c) for c in change.categories)
        lines.extend(
            [
                f"### {index}. {change.title} (`{change.change_id}`)",
                "",
                f"- **Type:** {change.change_type}",
                f"- **Importance:** {IMPORTANCE_LABELS[change.importance]} — {change.importance_reason}",
                f"- **Categories:** {categories or 'General'}",
                f"- **Section:** {change.section or '(none)'}",
                f"- **Pages:** previous={change.previous_page if change.previous_page is not None else 'n/a'}, "
                f"updated={change.updated_page if change.updated_page is not None else 'n/a'}",
                f"- **Evidence validated:** {'yes' if change.evidence_validated else 'no'}",
                "",
                "**Previous wording**",
                "",
                f"> {change.previous_text or '(none)'}",
                "",
                "**Updated wording**",
                "",
                f"> {change.updated_text or '(none)'}",
                "",
                "**Explanation (AI / heuristic interpretation)**",
                "",
                change.explanation,
                "",
                "**Possible practical implication**",
                "",
                change.impact,
                "",
                "**Review recommendation**",
                "",
                change.recommendation,
                "",
            ]
        )
        if change.numerical is not None:
            num = change.numerical
            lines.extend(
                [
                    "**Numerical delta**",
                    "",
                    f"- Direction: {num.direction}",
                    f"- Previous value: {num.previous_value}",
                    f"- Updated value: {num.updated_value}",
                    f"- Absolute difference: {num.absolute_difference}",
                    f"- Percentage difference: {num.percentage_difference}",
                    f"- Currency: {num.currency or 'n/a'}",
                    f"- Unit: {num.unit or 'n/a'}",
                    "",
                ]
            )

    lines.extend(["## Recommended review priorities", ""])
    if report.review_recommendations:
        for item in report.review_recommendations:
            lines.append(f"- {item}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Important", "", report.disclaimer, ""])

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _cell(value: str | None, limit: int = 48) -> str:
    if not value:
        return "—"
    text = " ".join(value.split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text.replace("|", "\\|")
