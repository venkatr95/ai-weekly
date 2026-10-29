"""Render an answer as Markdown. JSON uses the response model directly."""

from __future__ import annotations

from evidence_agent.schemas import AnswerResponse, Citation, RetrievedPassage


def render_markdown(response: AnswerResponse) -> str:
    citations = {citation.id: citation for citation in response.citations}
    lines = [
        "**Answer**",
        "",
        response.answer,
        "",
        "**Supported findings**",
        "",
    ]
    if not response.claims:
        lines.append("None.")
        lines.append("")
    for index, claim in enumerate(response.claims, start=1):
        lines.append(f"{index}. **Finding:** {claim.text}")
        lines.append("")
        for citation_id in claim.citation_ids:
            lines.extend(_citation_lines(citations.get(citation_id)))
        lines.append(f"   - Evidence status: {_label(claim.evidence_status)}")
        lines.append(f"   - Verification: {claim.verification_status}")
        lines.append("")

    lines.append("**Unanswered questions**")
    lines.append("")
    if not response.unanswered_questions:
        lines.append("None.")
        lines.append("")
    for item in response.unanswered_questions:
        lines.append(f"- {item.question}")
        lines.append(f"  - Reason: {item.reason}")
        lines.append(f"  - Detail: {item.detail}")
        for citation_id in item.citation_ids:
            citation = citations.get(citation_id)
            if citation:
                lines.append(f"  - Source: `{citation.source_path}`{_page(citation)}")
        lines.append("")

    lines.append("**Conflicts**")
    lines.append("")
    if not response.conflicts:
        lines.append("None.")
        lines.append("")
    for index, conflict in enumerate(response.conflicts, start=1):
        lines.append(f"{index}. **Topic:** {conflict.topic}")
        lines.append("")
        for position in conflict.positions:
            lines.append(f"   - Position: {position.summary}")
            for citation_id in position.citation_ids:
                lines.extend(_citation_lines(citations.get(citation_id), indent="     "))
        lines.append(f"   - Resolution: {'resolved' if conflict.resolved else 'unresolved'}")
        lines.append(f"   - Note: {conflict.note}")
        lines.append("")

    lines.append("**Limitations**")
    lines.append("")
    for note in response.limitations:
        lines.append(f"- {note}")
    lines.append("")
    lines.append(f"Provider: {response.provider}. Passages retrieved: {response.passages_retrieved}.")
    return "\n".join(lines).rstrip() + "\n"


def render_passages(passages: list[RetrievedPassage]) -> str:
    if not passages:
        return "Retrieved passages: none.\n"
    lines = ["Retrieved passages (ranking only; a score is not evidence):", ""]
    for index, passage in enumerate(passages, start=1):
        page = ""
        if passage.page_start is not None:
            page = f", pages {passage.page_start}-{passage.page_end}"
        lines.append(
            f"{index}. `{passage.relative_path}`{page} "
            f"score={passage.score:.3f} cosine={passage.cosine:.3f} lexical={passage.lexical:.3f} "
            f"chunk={passage.chunk_id}"
        )
        lines.append(passage.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _citation_lines(citation: Citation | None, indent: str = "   ") -> list[str]:
    if citation is None:
        return [f"{indent}- Source: missing citation"]
    return [
        f"{indent}- Source: `{citation.source_path}`{_page(citation)}",
        f"{indent}- Supporting passage: \"{citation.excerpt}\"",
    ]


def _page(citation: Citation) -> str:
    if citation.page is None:
        return ""
    return f", page {citation.page}"


def _label(value: str) -> str:
    return value[:1].upper() + value[1:]
