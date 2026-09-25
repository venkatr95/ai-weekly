"""Ask a question against the indexed documents."""

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_pipeline
from app.errors import GenerationError
from app.schemas.answer import QueryRequest, RAGResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=RAGResponse)
def query(body: QueryRequest, pipeline=Depends(get_pipeline)) -> RAGResponse:
    try:
        return pipeline.answer(body.question, top_k=body.top_k, debug=body.debug)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
