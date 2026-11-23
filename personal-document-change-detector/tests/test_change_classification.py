"""Category and importance heuristics."""

from document_detector.change_classifier import enrich_raw_change
from document_detector.text_diff import RawChange


def test_notice_period_is_high_priority():
    change = RawChange(
        change_type="modified",
        previous_text="Either party may terminate this agreement by giving 30 days written notice.",
        updated_text="Either party may terminate this agreement by giving 90 days written notice.",
        section="Notice Period",
        previous_section="Notice Period",
        updated_section="Notice Period",
        previous_page=1,
        updated_page=1,
    )
    meta = enrich_raw_change(change)
    assert meta["importance"] in {"high", "medium", "critical"}
    assert "dates_deadlines" in meta["categories"] or "numerical" in meta["categories"]


def test_formatting_is_informational():
    change = RawChange(
        change_type="modified",
        previous_text="Hello   world",
        updated_text="Hello world",
        section="Intro",
        previous_section="Intro",
        updated_section="Intro",
        previous_page=None,
        updated_page=None,
        formatting_only=True,
    )
    meta = enrich_raw_change(change)
    assert meta["importance"] == "informational"
