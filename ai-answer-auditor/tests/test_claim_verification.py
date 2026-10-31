from answer_auditor.claim_extractor import extract_claims_heuristic
from answer_auditor.claim_verifier import verify_claim
from answer_auditor.document_loader import load_sources
from answer_auditor.evidence_retriever import retrieve_evidence
from answer_auditor.textutil import percentage_change

ANNUAL = "Revenue for 2025 amounted to €120 million, compared with €100 million in 2024."
PROFIT = "Net profit for the financial year was €15 million."
WORKFORCE = "The company employed 460 people at the end of 2025, compared with 400 in 2024."


def _passages(claim: str, sources: list[dict]):
    documents, _warnings = load_sources(sources)
    return retrieve_evidence(claim, documents)


def _verdict(answer: str, sources: list[dict]):
    claim = extract_claims_heuristic(answer)[0]
    return verify_claim(claim, _passages(claim.text, sources))


def test_percentage_change_uses_the_baseline():
    assert percentage_change(120, 100) == 20
    assert percentage_change(460, 400) == 15


def test_direct_figure_is_supported_and_quoted():
    verdict = _verdict(
        "The company generated €120 million in revenue in 2025.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
    )
    assert verdict.status == "supported"
    assert verdict.supporting[0].quote == ANNUAL
    assert verdict.contradicting == []


def test_wrong_percentage_is_contradicted_by_the_calculation():
    verdict = _verdict(
        "Revenue increased by 25%.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
    )
    assert verdict.status == "contradicted"
    assert "20%" in verdict.explanation
    assert "€120 million" in verdict.contradicting[0].quote


def test_matching_implied_percentage_is_only_partially_supported():
    verdict = _verdict(
        "Revenue increased by 20%.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
    )
    assert verdict.status == "partially_supported"
    assert verdict.reason == "implied_calculation"
    assert verdict.supporting[0].source_id == "S1"


def test_explicit_percentage_is_supported():
    verdict = _verdict(
        "Revenue increased by 20%.",
        [{"source_id": "S1", "title": "Annual report", "text": "Revenue increased by 20% in 2025."}],
    )
    assert verdict.status == "supported"


def test_conflicting_profit_figure_is_contradicted():
    verdict = _verdict(
        "The company achieved a net profit of €18 million.",
        [{"source_id": "S2", "title": "Financial statement", "text": PROFIT}],
    )
    assert verdict.status == "contradicted"
    assert "€15 million" in verdict.explanation
    assert verdict.contradicting[0].quote == PROFIT


def test_workforce_growth_is_partial_because_the_percentage_is_not_stated():
    verdict = _verdict(
        "The company expanded its workforce by 15%.",
        [{"source_id": "S3", "title": "Workforce report", "text": WORKFORCE}],
    )
    assert verdict.status == "partially_supported"
    assert "460" in verdict.supporting[0].quote
    assert "400" in verdict.supporting[0].quote


def test_missing_evidence_is_unsupported_rather_than_contradicted():
    verdict = _verdict(
        "The company opened an office in Tokyo.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
    )
    assert verdict.status == "unsupported"
    assert verdict.contradicting == []
    assert "not a contradiction" in verdict.explanation


def test_opinion_is_unverifiable():
    verdict = _verdict(
        "I think this was an excellent year.",
        [{"source_id": "S1", "title": "Annual report", "text": ANNUAL}],
    )
    assert verdict.status == "unverifiable"


def test_conflicting_sources_are_both_preserved():
    verdict = _verdict(
        "Revenue was €10 million.",
        [
            {"source_id": "S1", "title": "Draft", "text": "Revenue was €10 million."},
            {"source_id": "S2", "title": "Final", "text": "Revenue was €12 million."},
        ],
    )
    assert verdict.status == "partially_supported"
    assert {item.source_id for item in verdict.supporting} == {"S1"}
    assert {item.source_id for item in verdict.contradicting} == {"S2"}


def test_negation_contradicts_a_matching_number():
    verdict = _verdict(
        "The company achieved a net profit of €15 million.",
        [
            {
                "source_id": "S1",
                "title": "Financial statement",
                "text": "The company did not achieve a net profit of €15 million.",
            }
        ],
    )
    assert verdict.status == "contradicted"


def test_extra_scope_is_partial():
    verdict = _verdict(
        "Revenue was €120 million in Europe.",
        [{"source_id": "S1", "title": "Annual report", "text": "Revenue was €120 million."}],
    )
    assert verdict.status == "partially_supported"
    assert "Europe" in verdict.explanation
