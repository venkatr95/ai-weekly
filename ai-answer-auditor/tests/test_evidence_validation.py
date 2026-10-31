from answer_auditor.claim_extractor import extract_claims_heuristic
from answer_auditor.document_loader import load_sources
from answer_auditor.evidence_validator import quote_is_in_source, validate_claim_evidence
from answer_auditor.schemas import EvidenceExcerpt


def test_real_quote_is_kept_and_invented_quote_is_dropped():
    documents, _warnings = load_sources(
        [{"source_id": "S1", "title": "Annual report", "text": "Revenue for 2025 amounted to €120 million."}]
    )
    claim = extract_claims_heuristic("Revenue was €120 million.")[0]
    real = EvidenceExcerpt(source_id="S1", quote="amounted to €120 million", page=None)
    fake = EvidenceExcerpt(source_id="S1", quote="Revenue was exactly one hundred twenty million euros.", page=None)
    assert quote_is_in_source(real, documents)
    assert not quote_is_in_source(fake, documents)
    status, _explanation, supporting, contradicting, notes = validate_claim_evidence(
        claim,
        "supported",
        "The model says this is supported.",
        [fake],
        [],
        [],
        documents,
    )
    assert status == "unsupported"
    assert supporting == []
    assert contradicting == []
    assert any("not found" in note or "does not appear" in note for note in notes)


def test_whitespace_differences_still_match_the_source_slice():
    documents, _warnings = load_sources(
        [{"source_id": "S1", "title": "Annual report", "text": "Revenue   for 2025\namounted to €120 million."}]
    )
    claim = extract_claims_heuristic("Revenue was €120 million.")[0]
    quote = EvidenceExcerpt(source_id="S1", quote="Revenue for 2025 amounted to €120 million.", page=None)
    status, _explanation, supporting, _contradicting, _notes = validate_claim_evidence(
        claim,
        "supported",
        "Supported.",
        [quote],
        [],
        [],
        documents,
    )
    assert status == "supported"
    assert supporting[0].quote == "Revenue   for 2025\namounted to €120 million."


def test_contradiction_without_a_real_quote_is_not_kept():
    documents, _warnings = load_sources(
        [{"source_id": "S1", "title": "Annual report", "text": "Revenue for 2025 amounted to €120 million."}]
    )
    claim = extract_claims_heuristic("Revenue was €1 million.")[0]
    status, explanation, _supporting, contradicting, _notes = validate_claim_evidence(
        claim,
        "contradicted",
        "Invented conflict.",
        [],
        [EvidenceExcerpt(source_id="S1", quote="Revenue was €1 million in the secret ledger.", page=None)],
        [],
        documents,
    )
    assert status == "unsupported"
    assert contradicting == []
    assert "not a contradiction" in explanation
