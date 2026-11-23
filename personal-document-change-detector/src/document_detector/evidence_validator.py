"""Verify that reported quotations appear in the extracted source documents."""

from __future__ import annotations

from document_detector.schemas import ChangeRecord, DocumentVersion
from document_detector.textutil import contains_quote


def validate_change(
    change: ChangeRecord,
    previous: DocumentVersion,
    updated: DocumentVersion,
) -> ChangeRecord:
    warnings: list[str] = []
    prev_ok = True
    upd_ok = True
    prev_text = previous.full_text()
    upd_text = updated.full_text()

    if change.previous_text:
        prev_ok = contains_quote(prev_text, change.previous_text)
        if not prev_ok:
            warnings.append("previous_text was not found verbatim in the previous document.")
    if change.updated_text:
        upd_ok = contains_quote(upd_text, change.updated_text)
        if not upd_ok:
            warnings.append("updated_text was not found verbatim in the updated document.")

    validated = prev_ok and upd_ok
    update: dict = {"evidence_validated": validated}
    if warnings:
        # Keep the change, but mark validation failure in the impact/explanation notes.
        note = " Evidence check: " + " ".join(warnings)
        update["explanation"] = change.explanation + note
    return change.model_copy(update=update)


def validate_report_changes(
    changes: list[ChangeRecord],
    previous: DocumentVersion,
    updated: DocumentVersion,
) -> tuple[list[ChangeRecord], list[str]]:
    validated: list[ChangeRecord] = []
    warnings: list[str] = []
    for change in changes:
        item = validate_change(change, previous, updated)
        validated.append(item)
        if not item.evidence_validated:
            warnings.append(f"{change.change_id} failed evidence validation.")
    return validated, warnings
