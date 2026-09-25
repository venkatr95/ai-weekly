from app.retrieval.reranker import Reranker
from app.schemas.answer import RetrievedChunk


def _chunk(chunk_id: str, text: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="doc_1",
        filename="policy.md",
        page=None,
        score=score,
        vector_score=score,
        text=text,
    )


def test_lexical_overlap_can_outrank_a_weaker_vector_hit():
    wrong = _chunk("chunk_b", "The office is closed on federal holidays.", 0.9)
    right = _chunk("chunk_a", "The refund period is 30 days.", 0.4)
    ranked = Reranker(0.45).rerank("What is the refund period?", [wrong, right], top_k=2)
    assert ranked[0].chunk_id == "chunk_a"
    assert ranked[0].score > ranked[1].score


def test_pure_vector_weight_keeps_the_vector_order():
    wrong = _chunk("chunk_b", "The office is closed on federal holidays.", 0.9)
    right = _chunk("chunk_a", "The refund period is 30 days.", 0.4)
    ranked = Reranker(1.0).rerank("What is the refund period?", [wrong, right], top_k=1)
    assert ranked[0].chunk_id == "chunk_b"
