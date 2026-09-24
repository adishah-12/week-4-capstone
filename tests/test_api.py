"""Tests for the FastAPI layer.

All Claude/agent dependencies are overridden via app.dependency_overrides --
these tests never trigger a real Claude client or Chroma embedding download.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import api.main as api_main


@pytest.fixture
def client():
    with TestClient(api_main.app) as c:
        yield c
    api_main.app.dependency_overrides.clear()


class TestHealth:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestQueryEndpoint:
    def test_query_delegates_to_manager_and_returns_its_result(self, client):
        fake_manager = MagicMock()
        fake_manager.answer.return_value = {"answer": "merged answer", "routed_to": "both"}
        api_main.app.dependency_overrides[api_main.get_manager] = lambda: fake_manager

        response = client.post("/query", json={"question": "test question"})

        assert response.status_code == 200
        assert response.json() == {"answer": "merged answer", "routed_to": "both"}
        fake_manager.answer.assert_called_once_with("test question")

    def test_query_missing_question_field_returns_422(self, client):
        # FastAPI resolves Depends(get_manager) even when body validation is
        # about to fail, so it must still be overridden here.
        api_main.app.dependency_overrides[api_main.get_manager] = lambda: MagicMock()

        response = client.post("/query", json={})

        assert response.status_code == 422


class TestQualitativeEndpoint:
    def test_returns_answer_and_sources(self, client):
        fake_agent = MagicMock()
        fake_agent.query.return_value = {
            "answer": "qual answer",
            "sources": [
                {"source": "security_policy.md", "chunk_id": "security_policy.md::2", "distance": 0.65}
            ],
        }
        api_main.app.dependency_overrides[api_main.get_qualitative_agent] = lambda: fake_agent

        response = client.post("/qualitative/query", json={"question": "security question"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "qual answer"
        assert body["sources"][0]["source"] == "security_policy.md"
        assert body["sources"][0]["distance"] == 0.65

    def test_empty_sources_list_is_valid(self, client):
        fake_agent = MagicMock()
        fake_agent.query.return_value = {"answer": "not found", "sources": []}
        api_main.app.dependency_overrides[api_main.get_qualitative_agent] = lambda: fake_agent

        response = client.post("/qualitative/query", json={"question": "unanswerable"})

        assert response.status_code == 200
        assert response.json()["sources"] == []


class TestQuantitativeEndpoint:
    def test_sqlite_tuples_serialize_to_json_lists(self, client):
        fake_agent = MagicMock()
        fake_agent.query.return_value = {
            "answer": "region | revenue\nNA | 100.0",
            "sql": "SELECT region, revenue FROM sales",
            "columns": ["region", "revenue"],
            "rows": [("North America", 100.0), ("EMEA", 50.0)],
        }
        api_main.app.dependency_overrides[api_main.get_quantitative_agent] = lambda: fake_agent

        response = client.post("/quantitative/query", json={"question": "revenue question"})

        assert response.status_code == 200
        assert response.json()["rows"] == [["North America", 100.0], ["EMEA", 50.0]]

    def test_null_sql_is_valid_for_unanswerable_questions(self, client):
        fake_agent = MagicMock()
        fake_agent.query.return_value = {
            "answer": "I don't have enough information.",
            "sql": None,
            "columns": [],
            "rows": [],
        }
        api_main.app.dependency_overrides[api_main.get_quantitative_agent] = lambda: fake_agent

        response = client.post("/quantitative/query", json={"question": "unanswerable"})

        assert response.status_code == 200
        assert response.json()["sql"] is None


class TestOpenAPIDocs:
    def test_openapi_schema_includes_all_routes(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = set(response.json()["paths"].keys())
        assert paths == {"/health", "/query", "/qualitative/query", "/quantitative/query"}

    def test_docs_ui_renders(self, client):
        response = client.get("/docs")
        assert response.status_code == 200
