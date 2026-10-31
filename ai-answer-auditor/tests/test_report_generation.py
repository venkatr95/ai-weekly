import json

from pydantic import ValidationError
import pytest

from answer_auditor.pipeline import audit
from answer_auditor.report_generator import render_json, render_markdown
from answer_auditor.schemas import AuditReport, ClaimResult, Summary
from answer_auditor.security import scrub_text


ANNUAL = "Revenue for 2025 amounted to €120 million, compared with €100 million in 2024."


def test_markdown_and_json_include_the_decision_and_the_excerpt():
    report = audit(
        "The company generated €120 million in revenue in 2025.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
        question="What was 2025 revenue?",
    )
    markdown = render_markdown(report)
    payload = json.loads(render_json(report))
    assert "Executive summary" in markdown
    assert "Supported" in markdown
    assert ANNUAL in markdown
    assert "Recommended review actions" in markdown
    assert payload["question"] == "What was 2025 revenue?"
    assert payload["summary"]["supported"] == 1
    assert payload["summary"]["evidence_coverage"] == 100.0
    assert payload["claims"][0]["supporting_evidence"][0]["quote"] == ANNUAL
    AuditReport.model_validate(payload)


def test_partial_support_is_not_counted_as_full_support():
    report = audit(
        "I think this was an excellent year. Revenue increased by 20%.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
    )
    assert report.summary.total_claims == 2
    assert report.summary.factual_claims == 1
    assert report.summary.partially_supported == 1
    assert report.summary.supported == 0
    assert report.summary.unverifiable == 1
    assert report.summary.evidence_coverage == 0.0


def test_schema_rejects_a_coverage_figure_that_counts_partial_support():
    claim = ClaimResult(
        claim_id="C001",
        text="Revenue increased by 20%.",
        claim_type="factual",
        status="partially_supported",
        explanation="Implied.",
        sentence_index=1,
        paragraph_index=1,
        original_sentence="Revenue increased by 20%.",
    )
    with pytest.raises(ValidationError):
        AuditReport(
            overall_assessment="Mixed.",
            summary=Summary(
                total_claims=1,
                supported=1,
                partially_supported=0,
                contradicted=0,
                unsupported=0,
                unverifiable=0,
                factual_claims=1,
                evidence_coverage=100.0,
            ),
            claims=[claim],
            provider="heuristic",
        )


def test_secrets_are_redacted():
    assert "xai-SECRETKEY12345" not in scrub_text("contact xai-SECRETKEY12345 now")
    assert "[redacted]" in scrub_text("contact xai-SECRETKEY12345 now")
