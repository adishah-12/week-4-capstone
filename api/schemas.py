"""Pydantic request/response schemas for the API layer."""

from typing import Any

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class SourceCitation(BaseModel):
    source: str
    chunk_id: str | None = None
    distance: float | None = None


class QueryResponse(BaseModel):
    answer: str
    routed_to: str


class QualitativeQueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = []


class QuantitativeQueryResponse(BaseModel):
    answer: str
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[Any]] = []


class HealthResponse(BaseModel):
    status: str
