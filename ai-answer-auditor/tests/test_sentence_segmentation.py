from answer_auditor.sentence_segmenter import segment_answer, split_sentences


def test_splits_on_sentence_boundaries():
    sentences = split_sentences("Revenue rose. Costs fell. Hiring stayed flat.")
    assert sentences == ["Revenue rose.", "Costs fell.", "Hiring stayed flat."]


def test_keeps_decimals_and_abbreviations_inside_the_sentence():
    sentences = split_sentences("Mr. Smith reported a ratio of 3.14. Revenue rose afterwards.")
    assert sentences == ["Mr. Smith reported a ratio of 3.14.", "Revenue rose afterwards."]


def test_paragraph_indexes_are_preserved():
    segments = segment_answer("Revenue rose.\n\nCosts fell.")
    assert [(segment.paragraph_index, segment.sentence_index, segment.text) for segment in segments] == [
        (1, 1, "Revenue rose."),
        (2, 2, "Costs fell."),
    ]
