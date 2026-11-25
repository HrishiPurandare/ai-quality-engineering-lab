"""HTTP API for the "NovaAsk" assistant.

Run: uvicorn app.main:app --reload
"""

from dataclasses import asdict
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.ingest import build_store, ingest
from app.llm import OllamaClient, OllamaError
from app.rag import RAGPipeline

app = FastAPI(title="NovaAsk", version="0.2.0")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class CitationOut(BaseModel):
    number: int
    source: str
    section: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationOut]
    contexts: list[str]
    refused: bool
    guardrails: list[str]


@lru_cache
def get_pipeline() -> RAGPipeline:
    llm = OllamaClient(settings)
    return RAGPipeline(build_store(llm), llm, settings.top_k, settings.max_distance, settings.guardrails)


Pipeline = Annotated[RAGPipeline, Depends(get_pipeline)]


@app.get("/health")
def health(pipeline: Pipeline) -> dict:
    return {"status": "ok", "indexed_chunks": pipeline.store.count()}


@app.post("/ingest")
def reindex(pipeline: Pipeline) -> dict:
    return {"indexed_chunks": ingest(pipeline.store, settings)}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, pipeline: Pipeline) -> dict:
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be blank")
    try:
        return asdict(pipeline.ask(request.question))
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
