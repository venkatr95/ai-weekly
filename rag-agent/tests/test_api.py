from app.sample_pdf import build_refund_policy_pdf
from app.schemas.answer import INSUFFICIENT_ANSWER


REFUND = (
    b"# Refund\n\n"
    b"The refund period is 30 days. Customers may request a refund within 30 days "
    b"of the original purchase date.\n"
)


def test_upload_query_and_read_back(client):
    uploaded = client.post(
        "/v1/documents",
        files={"file": ("refund-policy.md", REFUND, "text/markdown")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["status"] == "indexed"
    assert body["chunks"] >= 1
    document_id = body["document_id"]

    fetched = client.get(f"/v1/documents/{document_id}")
    assert fetched.status_code == 200
    assert fetched.json()["filename"] == "refund-policy.md"
    assert fetched.json()["content_type"] == "text/markdown"
    assert fetched.json()["chunk_count"] == body["chunks"]

    answer = client.post(
        "/v1/query",
        json={"question": "What is the refund period?", "debug": True},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert "30 days" in payload["answer"]
    assert payload["citations"][0]["document"] == "refund-policy.md"
    assert payload["citations"][0]["chunk_id"]
    assert payload["retrieved"][0]["chunk_id"] == payload["citations"][0]["chunk_id"]
    assert "score" in payload["retrieved"][0]
    assert payload["retrieved"][0]["text"]


def test_missing_document_is_404(client):
    response = client.get("/v1/documents/doc_missing")
    assert response.status_code == 404


def test_unsupported_upload_and_empty_question(client):
    rejected = client.post(
        "/v1/documents",
        files={"file": ("notes.docx", b"hello", "application/octet-stream")},
    )
    assert rejected.status_code == 415
    empty = client.post("/v1/query", json={"question": "   "})
    assert empty.status_code == 422


def test_path_in_filename_is_stripped(client):
    uploaded = client.post(
        "/v1/documents",
        files={"file": ("../refund-policy.md", REFUND, "text/markdown")},
    )
    assert uploaded.status_code == 200
    document_id = uploaded.json()["document_id"]
    assert client.get(f"/v1/documents/{document_id}").json()["filename"] == "refund-policy.md"


def test_pdf_citation_names_page_4(client):
    uploaded = client.post(
        "/v1/documents",
        files={"file": ("refund-policy.pdf", build_refund_policy_pdf(), "application/pdf")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["chunks"] >= 4
    answer = client.post("/v1/query", json={"question": "What is the refund period?"})
    assert answer.status_code == 200
    payload = answer.json()
    assert "30 days" in payload["answer"]
    assert payload["citations"][0]["document"] == "refund-policy.pdf"
    assert payload["citations"][0]["page"] == 4


def test_revenue_question_is_refused(client):
    client.post("/v1/documents", files={"file": ("refund-policy.md", REFUND, "text/markdown")})
    answer = client.post("/v1/query", json={"question": "What is the company's annual revenue?"})
    assert answer.status_code == 200
    assert answer.json()["answer"] == INSUFFICIENT_ANSWER
    assert answer.json()["citations"] == []
    assert "retrieved" not in answer.json()


def test_health(client):
    payload = client.get("/health").json()
    assert payload["status"] == "ok"
    assert payload["embedding_provider"] == "hashing"
    assert payload["llm_provider"] == "extractive"
    assert payload["vector_store"] == "memory"
