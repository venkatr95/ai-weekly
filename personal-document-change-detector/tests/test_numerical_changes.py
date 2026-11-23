"""Numerical and obligation change detection."""

from document_detector.impact_analyzer import compare_numerical, obligation_shift


def test_salary_percentage_change():
    delta = compare_numerical("Annual salary: €60,000.", "Annual salary: €65,000.")
    assert delta is not None
    assert delta.direction == "increased"
    assert delta.previous_value == 60000
    assert delta.updated_value == 65000
    assert delta.currency == "€"
    assert delta.percentage_difference == 8.33


def test_zero_base_skips_percentage():
    delta = compare_numerical("Balance: €0", "Balance: €100")
    assert delta is not None
    assert delta.percentage_difference is None
    assert delta.absolute_difference == 100


def test_obligation_weakening():
    note = obligation_shift(
        "The supplier shall deliver the product within 30 days.",
        "The supplier should aim to deliver the product within 30 days.",
    )
    assert note is not None
    assert "weakened" in note.lower()


def test_word_number_days():
    delta = compare_numerical(
        "The employee may work remotely up to three days per week.",
        "The employee may work remotely up to one day per week.",
    )
    assert delta is not None
    assert delta.previous_value == 3
    assert delta.updated_value == 1
    assert delta.direction == "decreased"
    assert delta.unit == "day"
