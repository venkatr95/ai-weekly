import math

from app.ingestion.embedder import HashingEmbedder


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def test_hashing_embedder_is_deterministic_and_unit_length():
    embedder = HashingEmbedder(128)
    first = embedder.embed_query("The refund period is 30 days.")
    second = embedder.embed_texts(["The refund period is 30 days."])[0]
    assert first == second
    assert len(first) == 128
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0, rel_tol=1e-6)


def test_related_text_is_closer_than_unrelated_text():
    embedder = HashingEmbedder()
    query = embedder.embed_query("What is the refund period?")
    refund = embedder.embed_query("The refund period is 30 days.")
    holiday = embedder.embed_query("The office is closed on federal holidays.")
    assert _cosine(query, refund) > _cosine(query, holiday) + 0.05
