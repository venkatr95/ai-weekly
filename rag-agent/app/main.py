"""FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.config import get_settings
from app.logging_config import configure_logging
from app.pipeline import RAGPipeline, build_pipeline


def create_app(pipeline: RAGPipeline | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if pipeline is None:
            settings = get_settings()
            configure_logging(settings.log_level)
            app.state.pipeline = build_pipeline(settings)
        else:
            app.state.pipeline = pipeline
        yield

    app = FastAPI(
        title="RAG Agent",
        version="0.1.0",
        summary="Answers questions from uploaded documents and cites the retrieved chunks.",
        lifespan=lifespan,
    )
    app.include_router(documents_router, prefix="/v1")
    app.include_router(query_router, prefix="/v1")

    @app.get("/health", tags=["health"])
    def health(request: Request) -> dict[str, str]:
        current = getattr(request.app.state, "pipeline", None)
        if current is None:
            return {"status": "starting"}
        return {
            "status": "ok",
            "vector_store": current.settings.vector_store,
            "embedding_provider": current.embedder.name,
            "llm_provider": current.generator.name,
        }

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": "rag-agent", "docs": "/docs", "health": "/health"}

    return app


app = create_app()
