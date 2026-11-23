"""Evidence validation rejects invented quotations."""

from document_detector.evidence_validator import validate_change
from document_detector.schemas import ChangeRecord, DocumentVersion, PageText


def _doc(document_id: str, text: str) -> DocumentVersion:
    return DocumentVersion(
        document_id=document_id,
        filename=f"{document_id}.txt",
        file_type="txt",
        pages=[PageText(page_number=1, text=text)],
    )


def test_valid_and_invalid_quotes():
    previous = _doc("previous", "Annual salary: €60,000.")
    updated = _doc("updated", "Annual salary: €65,000.")
    good = ChangeRecord(
        change_id="CH001",
        change_type="modified",
        categories=["financial"],
        importance="medium",
        importance_reason="money",
        title="Salary",
        previous_text="Annual salary: €60,000.",
        updated_text="Annual salary: €65,000.",
        explanation="Salary increased.",
        impact="Higher pay.",
        recommendation="Confirm.",
        previous_document_id="previous",
        updated_document_id="updated",
    )
    assert validate_change(good, previous, updated).evidence_validated is True

    bad = good.model_copy(update={"previous_text": "Annual salary: €99,000."})
    assert validate_change(bad, previous, updated).evidence_validated is False
