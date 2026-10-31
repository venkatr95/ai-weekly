from answer_auditor.claim_extractor import extract_claims_heuristic


def test_splits_a_compound_sentence_into_the_original_clauses():
    claims = extract_claims_heuristic("Revenue increased by 20%, and the company hired 100 employees.")
    assert [claim.text for claim in claims] == [
        "Revenue increased by 20%.",
        "The company hired 100 employees.",
    ]
    assert [claim.claim_id for claim in claims] == ["C001", "C002"]
    assert all(claim.claim_type == "factual" for claim in claims)


def test_carries_the_subject_onto_a_verb_phrase():
    claims = extract_claims_heuristic(
        "The company also achieved a net profit of €18 million and expanded its workforce by 15%."
    )
    assert [claim.text for claim in claims] == [
        "The company also achieved a net profit of €18 million.",
        "The company expanded its workforce by 15%.",
    ]


def test_does_not_invent_claims_or_split_a_single_fact():
    claims = extract_claims_heuristic("The company generated €120 million in revenue in 2025.")
    assert len(claims) == 1
    assert claims[0].text == "The company generated €120 million in revenue in 2025."
    assert "dividend" not in claims[0].text


def test_labels_opinions_recommendations_and_non_factual_text():
    claims = extract_claims_heuristic(
        "I think this was an excellent year. The company should hire more staff. Thank you for reading."
    )
    assert [claim.claim_type for claim in claims] == ["opinion", "recommendation", "non_factual"]


def test_keeps_sentence_and_paragraph_references():
    claims = extract_claims_heuristic("Revenue rose by 10%.\n\nCosts fell by 2%.")
    assert [(claim.paragraph_index, claim.sentence_index) for claim in claims] == [(1, 1), (2, 2)]
    assert claims[0].original_sentence == "Revenue rose by 10%."
