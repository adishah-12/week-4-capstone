"""FastAPI layer over the manager and both sub-agents.

    uv run uvicorn api.main:app --reload

Interactive OpenAPI docs are auto-generated at /docs (Swagger UI) and /redoc.
"""

import logging
import os
from functools import lru_cache

from anthropic import Anthropic
from fastapi import Depends, FastAPI

from agents.manager import ManagerAgent
from agents.qualitative import QualitativeAgent
from agents.quantitative import QuantitativeAgent
from api.schemas import (
    HealthResponse,
    QualitativeQueryResponse,
    QuantitativeQueryResponse,
    QueryRequest,
    QueryResponse,
)
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-Agent RAG System",
    description="Routes enterprise documentation questions to a qualitative "
    "(RAG) agent, a quantitative (NL-to-SQL) agent, or both.",
    version="0.1.0",
)


# Dependencies are lazily-constructed singletons (lru_cache), not built at
# import time or in a startup event -- this means importing api.main (e.g.
# from a test) never triggers a real Claude client or a Chroma embedding
# download. Tests override these via app.dependency_overrides instead of
# ever calling the real functions.
@lru_cache
def get_claude_client() -> Anthropic:
    # See cli.py for why ANTHROPIC_WORKSPACE_ID may be needed for
    # organization-level (non-workspace-scoped) API keys.
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    default_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    return Anthropic(default_headers=default_headers)


@lru_cache
def get_qualitative_agent() -> QualitativeAgent:
    agent = QualitativeAgent(claude_client=get_claude_client())
    agent.ingest()
    return agent


@lru_cache
def get_quantitative_agent() -> QuantitativeAgent:
    return QuantitativeAgent(claude_client=get_claude_client())


@lru_cache
def get_manager() -> ManagerAgent:
    return ManagerAgent(
        claude_client=get_claude_client(),
        qualitative_agent=get_qualitative_agent(),
        quantitative_agent=get_quantitative_agent(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, manager: ManagerAgent = Depends(get_manager)) -> QueryResponse:
    result = manager.answer(request.question)
    return QueryResponse(answer=result["answer"], routed_to=result["routed_to"])


@app.post("/qualitative/query", response_model=QualitativeQueryResponse)
def qualitative_query(
    request: QueryRequest, agent: QualitativeAgent = Depends(get_qualitative_agent)
) -> QualitativeQueryResponse:
    result = agent.query(request.question)
    return QualitativeQueryResponse(answer=result["answer"], sources=result["sources"])


@app.post("/quantitative/query", response_model=QuantitativeQueryResponse)
def quantitative_query(
    request: QueryRequest, agent: QuantitativeAgent = Depends(get_quantitative_agent)
) -> QuantitativeQueryResponse:
    result = agent.query(request.question)
    return QuantitativeQueryResponse(
        answer=result["answer"],
        sql=result["sql"],
        columns=result["columns"],
        rows=[list(row) for row in result["rows"]],
    )
