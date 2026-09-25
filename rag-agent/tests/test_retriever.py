def test_refund_question_retrieves_the_refund_chunk(pipeline):
    pipeline.ingest(
        "refund-policy.md",
        b"The refund period is 30 days. Customers may request a refund within 30 days.",
        "text/markdown",
    )
    pipeline.ingest(
        "holiday.md",
        b"The office is closed on federal holidays and the parking lot is empty.",
        "text/markdown",
    )
    found = pipeline.retriever.retrieve("What is the refund period?", top_k=2)
    assert len(found) == 2
    assert found[0].filename == "refund-policy.md"
    assert found[0].score >= found[1].score
    assert "30 days" in found[0].text
    assert found[0].document_id
    assert found[0].chunk_id.startswith("chunk_")


def test_top_k_limits_the_result(pipeline):
    for index in range(4):
        pipeline.ingest(
            f"note-{index}.txt",
            f"Topic {index} discusses shipping lanes and warehouse hours.".encode(),
            "text/plain",
        )
    found = pipeline.retriever.retrieve("warehouse hours", top_k=2)
    assert len(found) == 2
