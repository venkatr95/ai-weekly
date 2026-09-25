"""Shared pipeline and API client. Both stay in memory and never call a model API."""

import pytest
from fastapi.testclient import TestClient

from app.config import make_settings
from app.main import create_app
from app.pipeline import build_pipeline


def build_test_pipeline(**overrides):
    settings = make_settings(
        vector_store="memory",
        embedding_provider="hashing",
        llm_provider="extractive",
        chunk_size_tokens=500,
        chunk_overlap_tokens=100,
        **overrides,
    )
    return build_pipeline(settings)


@pytest.fixture
def pipeline():
    return build_test_pipeline()


@pytest.fixture
def client(pipeline):
    application = create_app(pipeline)
    with TestClient(application) as test_client:
        yield test_client
