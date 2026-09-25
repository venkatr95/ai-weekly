from evaluation.run_eval import (
    CITATION_ACCURACY_TARGET,
    GROUNDED_ANSWER_RATE_TARGET,
    RETRIEVAL_RECALL_TARGET,
    UNSUPPORTED_REFUSAL_TARGET,
    evaluate,
)


def test_sample_corpus_meets_the_quality_targets():
    report = evaluate()
    failures = [row for row in report["results"] if row["reasons"]]
    assert report["questions"] >= 15
    assert report["handbook_chunks"] >= 2
    assert report["retrieval_recall"] >= RETRIEVAL_RECALL_TARGET, failures
    assert report["citation_accuracy"] >= CITATION_ACCURACY_TARGET, failures
    assert report["grounded_answer_rate"] >= GROUNDED_ANSWER_RATE_TARGET, failures
    assert report["unsupported_refusal_rate"] >= UNSUPPORTED_REFUSAL_TARGET, failures
