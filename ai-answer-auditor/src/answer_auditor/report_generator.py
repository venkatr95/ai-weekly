"""Render a validated audit as Markdown or JSON."""

from __future__ import annotations

import json

from answer_auditor.schemas import STATUS_LABELS, AuditReport, ClaimResult, EvidenceExcerpt, Summary

_REVIEW = {
    "contradicted": "Correct or remove contradicted claims before the answer is reused: {ids}.",
    "unsupported": "Find a source or remove claims that the documents do not support: {ids}.",
    "partially_supported": "Qualify claims that the sources only partly establish: {ids}.",
    "unverifiable": "Label opinions, recommendations, and other non-checkable statements: {ids}.",
}


def build_summary(claims: list[ClaimResult]) -> Summary:
    counts = {status: 0 for status in STATUS_LABELS}
    for claim in claims:
        counts[claim.status] += 1
    factual = sum(1 for claim in claims if claim.claim_type == "factual")
    coverage = round(100.0 * counts["supported"] / factual, 1) if factual else None
    return Summary(
        total_claims=len(claims),
        supported=counts["supported"],
        partially_supported=counts["partially_supported"],
        contradicted=counts["contradicted"],
        unsupported=counts["unsupported"],
        unverifiable=counts["unverifiable"],
        factual_claims=factual,
        evidence_coverage=coverage,
    )


def overall_assessment(summary: Summary) -> str:
    labels: list[str] = []
    for status, label in (
        ("supported", "supported"),
        ("partially_supported", "partially supported"),
        ("contradicted", "contradicted"),
        ("unsupported", "unsupported"),
        ("unverifiable", "unverifiable"),
    ):
        if getattr(summary, status):
            labels.append(label)
    if not labels:
        return "No claims were extracted from the answer."
    if labels == ["supported"]:
        return "The answer is supported by the supplied sources."
    if len(labels) == 1:
        return f"The answer contains {labels[0]} claims."
    if len(labels) == 2:
        return f"The answer contains {labels[0]} and {labels[1]} claims."
    return "The answer contains " + ", ".join(labels[:-1]) + ", and " + labels[-1] + " claims."


def render_json(report: AuditReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)


def render_markdown(report: AuditReport) -> str:
    summary = report.summary
    coverage = "n/a" if summary.evidence_coverage is None else f"{summary.evidence_coverage:.1f}%"
    lines = [
        "# Verification report",
        "",
        "## Executive summary",
        "",
        report.overall_assessment,
        "",
    ]
    if report.question:
        lines.extend([f"**Question:** {report.question}", ""])
    lines.extend(
        [
            "Evidence coverage counts fully supported claims only. "
            "Partially supported claims are reported separately and are not treated as fully supported.",
            "",
            "## Verification statistics",
            "",
            "| Status | Count |",
            "| --- | ---: |",
            f"| Total claims | {summary.total_claims} |",
            f"| Factual claims | {summary.factual_claims} |",
            f"| Supported | {summary.supported} |",
            f"| Partially supported | {summary.partially_supported} |",
            f"| Contradicted | {summary.contradicted} |",
            f"| Unsupported | {summary.unsupported} |",
            f"| Unverifiable | {summary.unverifiable} |",
            f"| Evidence coverage | {coverage} |",
            "",
            "Evidence coverage is the number of supported claims divided by the number of factual claims.",
            "",
            "## Sources",
            "",
        ]
    )
    if not report.sources:
        lines.append("No sources were loaded.")
    else:
        lines.extend(["| ID | Title | Type | Pages |", "| --- | --- | --- | ---: |"])
        for source in report.sources:
            pages = "-" if source.page_count is None else str(source.page_count)
            title = source.title or source.path or ""
            lines.append(f"| {source.source_id} | {title} | {source.file_type} | {pages} |")
    lines.extend(["", "## Claim-by-claim results", ""])
    if not report.claims:
        lines.append("No claims were extracted.")
    for claim in report.claims:
        lines.extend(_render_claim(claim))
    lines.extend(["## Recommended review actions", ""])
    actions = _actions(report.claims)
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- No review actions. Every factual claim is supported by a source excerpt.")
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "## How to read this report",
            "",
            "A supported status means a source excerpt states the claim. "
            "A contradicted status means a source excerpt conflicts with it. "
            "An unsupported status means the supplied documents do not contain enough evidence. "
            "Absence of a passage is not treated as proof that the claim is false. "
            "This report does not decide whether the claim is true outside the supplied sources.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_claim(claim: ClaimResult) -> list[str]:
    lines = [
        f"### {claim.claim_id} — {STATUS_LABELS[claim.status]}",
        "",
        f"**Claim:** {claim.text}",
        "",
        f"**Type:** {claim.claim_type}",
        "",
        f"**Explanation:** {claim.explanation}",
        "",
        "**Supporting evidence:**",
        "",
    ]
    lines.extend(_render_evidence(claim.supporting_evidence))
    lines.extend(["", "**Contradicting evidence:**", ""])
    lines.extend(_render_evidence(claim.contradicting_evidence))
    lines.extend(["", "**Notes:**", ""])
    if claim.verification_notes:
        lines.extend(f"- {note}" for note in claim.verification_notes)
    else:
        lines.append("- None")
    lines.append("")
    return lines


def _render_evidence(excerpts: list[EvidenceExcerpt]) -> list[str]:
    if not excerpts:
        return ["- None"]
    lines: list[str] = []
    for excerpt in excerpts:
        page = "page not available" if excerpt.page is None else f"page {excerpt.page}"
        title = f", {excerpt.source_title}" if excerpt.source_title else ""
        lines.append(f"- {excerpt.source_id}{title}, {page}: \"{excerpt.quote}\"")
    return lines


def _actions(claims: list[ClaimResult]) -> list[str]:
    actions: list[str] = []
    for status, template in _REVIEW.items():
        ids = [claim.claim_id for claim in claims if claim.status == status]
        if ids:
            actions.append(template.format(ids=", ".join(ids)))
    return actions
