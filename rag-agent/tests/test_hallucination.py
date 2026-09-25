from app.schemas.answer import INSUFFICIENT_ANSWER, Claim, ModelAnswer


REFUND = b"The refund period is 30 days. Customers may request a refund within 30 days of purchase.\n"


class _FabricatingGenerator:
    name = "fabricator"
    calls = 0

    def generate(self, question, sources):
        self.calls += 1
        return ModelAnswer(
            sufficient=True,
            claims=[Claim(text="Annual revenue is 9 million.", citation_ids=[1])],
        )


def test_unsupported_question_is_refused_without_calling_the_generator(pipeline):
    pipeline.ingest("refund-policy.md", REFUND, "text/markdown")

    class _Counting:
        name = pipeline.generator.name
        calls = 0

        def __init__(self, inner):
            self.inner = inner

        def generate(self, question, sources):
            self.calls += 1
            return self.inner.generate(question, sources)

    counter = _Counting(pipeline.generator)
    pipeline.generator = counter
    response = pipeline.answer("What is the company's annual revenue?")
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []
    assert counter.calls == 0


def test_fabricated_claim_cannot_become_a_citation(pipeline):
    pipeline.ingest("refund-policy.md", REFUND, "text/markdown")
    pipeline.min_score = 0
    pipeline.generator = _FabricatingGenerator()
    response = pipeline.answer("What is the company's annual revenue?")
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []
    assert "million" not in response.answer


def test_copying_an_unrelated_chunk_does_not_answer_the_question(pipeline):
    pipeline.ingest("refund-policy.md", REFUND, "text/markdown")
    pipeline.min_score = 0

    class _OffTopic:
        name = "off-topic"

        def generate(self, question, sources):
            return ModelAnswer(
                sufficient=True,
                claims=[Claim(text="The refund period is 30 days.", citation_ids=[1])],
            )

    pipeline.generator = _OffTopic()
    response = pipeline.answer("What is the company's annual revenue?")
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []
