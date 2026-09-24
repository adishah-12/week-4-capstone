"""Shared fixtures for the test suite."""

import hashlib
import random
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from chromadb.api.types import EmbeddingFunction

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.seed_db import build_schema, seed_customers, seed_sales  # noqa: E402


class FakeEmbeddingFunction(EmbeddingFunction):
    """Deterministic, hash-based fake embedding -- no network or model
    download needed. NOT semantically meaningful: only suitable for testing
    pipeline mechanics (chunking, ingest, threshold branching), never for
    testing real retrieval quality. Real retrieval quality is covered
    separately by eval/retrieval_eval.py against the real embedding model.
    """

    def __init__(self):
        pass

    def __call__(self, input):
        return [[b / 255.0 for b in hashlib.sha256(t.encode()).digest()[:16]] for t in input]

    @staticmethod
    def name() -> str:
        return "fake"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "FakeEmbeddingFunction":
        return FakeEmbeddingFunction()


@pytest.fixture
def fake_embedding_function():
    return FakeEmbeddingFunction()


def _make_fake_claude(text: str) -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(type="text", text=text)])
    return client


@pytest.fixture
def fake_claude_factory():
    """Returns a function: call it with the text you want Claude to 'reply'
    with, get back a mocked Anthropic client.
    """
    return _make_fake_claude


@pytest.fixture
def temp_db(tmp_path):
    """A real, small SQLite database with the same schema as
    data/enterprise.db, seeded deterministically. Hermetic: never touches
    the real data/enterprise.db.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    try:
        rng = random.Random(1)
        build_schema(conn)
        seed_sales(conn, rng)
        seed_customers(conn, rng, n=50)
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture
def policies_dir(tmp_path):
    """A small, independent set of markdown docs for qualitative agent
    tests -- separate from the real data/policies corpus so tests don't
    depend on its exact wording.
    """
    d = tmp_path / "policies"
    d.mkdir()
    (d / "doc_a.md").write_text(
        "# Doc A\n\n## Section One\nContent about topic A.\n\n## Section Two\nMore A content."
    )
    (d / "doc_b.md").write_text("# Doc B\n\n## Section One\nContent about topic B.")
    return d
