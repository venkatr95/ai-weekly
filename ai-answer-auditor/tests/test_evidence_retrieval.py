from answer_auditor.document_loader import load_sources
from answer_auditor.evidence_retriever import retrieve_evidence

ANNUAL = "Revenue for 2025 amounted to €120 million, compared with €100 million in 2024."
PROFIT = "Net profit for the financial year was €15 million."
WORKFORCE = "The company employed 460 people at the end of 2025, compared with 400 in 2024."


def _documents():
    documents, _warnings = load_sources(
        [
            {"source_id": "S1", "title": "Annual report", "text": ANNUAL},
            {"source_id": "S2", "title": "Financial statement", "text": PROFIT},
            {"source_id": "S3", "title": "Workforce report", "text": WORKFORCE},
        ]
    )
    return documents


def test_retrieves_the_passage_that_shares_the_claim_metric():
    documents = _documents()
    revenue = retrieve_evidence("The company generated €120 million in revenue in 2025.", documents)
    profit = retrieve_evidence("The company achieved a net profit of €18 million.", documents)
    workforce = retrieve_evidence("The company expanded its workforce by 15%.", documents)
    assert revenue[0].source_id == "S1"
    assert "€120 million" in revenue[0].text
    assert profit[0].source_id == "S2"
    assert workforce[0].source_id == "S3"
    assert workforce[0].context


def test_does_not_retrieve_an_unrelated_passage_for_a_different_topic():
    documents = _documents()
    passages = retrieve_evidence("The company opened an office in Tokyo.", documents)
    assert passages == []


def test_pdf_page_number_is_kept_on_the_passage(tmp_path):
    from tests.pdf_util import write_text_pdf

    path = tmp_path / "report.pdf"
    write_text_pdf(path, ["Cover page.", "Revenue for 2025 amounted to EUR 120 million."])
    documents, _warnings = load_sources([path])
    passages = retrieve_evidence("Revenue was EUR 120 million in 2025.", documents)
    assert passages[0].page == 2
