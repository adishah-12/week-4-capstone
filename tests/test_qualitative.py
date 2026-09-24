"""Unit and integration tests for the qualitative RAG agent.

Uses a fake embedding function throughout (see conftest.py) -- these tests
verify pipeline mechanics (chunking, ingest, threshold branching, source
citation shape), not real retrieval quality. Real retrieval quality against
the actual embedding model is covered by eval/retrieval_eval.py.
"""

from agents.qualitative import QualitativeAgent, _chunk_markdown


class TestChunkMarkdown:
    def test_splits_on_h2_headers(self):
        text = "# Title\n\n## Section One\nContent A.\n\n## Section Two\nContent B."
        chunks = _chunk_markdown(text, source="doc.md")
        assert len(chunks) == 2
        assert "Section One" in chunks[0]["text"]
        assert "Section Two" in chunks[1]["text"]

    def test_folds_bare_title_into_first_section(self):
        text = "# Title Only\n\n## Purpose\nThe actual content."
        chunks = _chunk_markdown(text, source="doc.md")
        assert len(chunks) == 1
        assert "Title Only" in chunks[0]["text"]
        assert "The actual content." in chunks[0]["text"]

    def test_chunk_ids_are_unique_and_source_prefixed(self):
        text = "## A\ntext\n\n## B\ntext\n\n## C\ntext"
        chunks = _chunk_markdown(text, source="doc.md")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))
        assert all(cid.startswith("doc.md::") for cid in ids)

    def test_empty_document_produces_no_chunks(self):
        assert _chunk_markdown("", source="empty.md") == []


class TestIngest:
    def test_ingest_counts_chunks_across_all_docs(
        self, fake_claude_factory, fake_embedding_function, policies_dir, tmp_path
    ):
        agent = QualitativeAgent(
            claude_client=fake_claude_factory("unused"),
            docs_dir=policies_dir,
            chroma_path=tmp_path / "chroma",
            embedding_function=fake_embedding_function,
        )
        n = agent.ingest()
        assert n == 3

    def test_ingest_is_idempotent_by_default(
        self, fake_claude_factory, fake_embedding_function, policies_dir, tmp_path
    ):
        agent = QualitativeAgent(
            claude_client=fake_claude_factory("unused"),
            docs_dir=policies_dir,
            chroma_path=tmp_path / "chroma",
            embedding_function=fake_embedding_function,
        )
        first = agent.ingest()
        second = agent.ingest()
        assert first == second == 3

    def test_ingest_force_rebuilds(
        self, fake_claude_factory, fake_embedding_function, policies_dir, tmp_path
    ):
        agent = QualitativeAgent(
            claude_client=fake_claude_factory("unused"),
            docs_dir=policies_dir,
            chroma_path=tmp_path / "chroma",
            embedding_function=fake_embedding_function,
        )
        agent.ingest()
        n = agent.ingest(force=True)
        assert n == 3


class TestQuery:
    def _agent(self, claude_client, embedding_function, policies_dir, tmp_path, threshold):
        agent = QualitativeAgent(
            claude_client=claude_client,
            docs_dir=policies_dir,
            chroma_path=tmp_path / "chroma",
            embedding_function=embedding_function,
            relevance_threshold=threshold,
        )
        agent.ingest()
        return agent

    def test_query_above_threshold_calls_claude_and_returns_answer(
        self, fake_claude_factory, fake_embedding_function, policies_dir, tmp_path
    ):
        claude = fake_claude_factory("synthesized answer")
        agent = self._agent(claude, fake_embedding_function, policies_dir, tmp_path, threshold=999)

        result = agent.query("What is topic A?")

        assert result["answer"] == "synthesized answer"
        assert len(result["sources"]) > 0
        claude.messages.create.assert_called_once()
        assert claude.messages.create.call_args.kwargs["model"] == "claude-haiku-4-5"

    def test_query_below_threshold_returns_not_found_without_calling_claude(
        self, fake_claude_factory, fake_embedding_function, policies_dir, tmp_path
    ):
        claude = fake_claude_factory("should not be used")
        agent = self._agent(claude, fake_embedding_function, policies_dir, tmp_path, threshold=-1)

        result = agent.query("anything")

        assert result["sources"] == []
        assert "couldn't find" in result["answer"].lower()
        claude.messages.create.assert_not_called()

    def test_query_sources_include_source_chunk_id_and_distance(
        self, fake_claude_factory, fake_embedding_function, policies_dir, tmp_path
    ):
        claude = fake_claude_factory("answer")
        agent = self._agent(claude, fake_embedding_function, policies_dir, tmp_path, threshold=999)

        result = agent.query("anything")

        assert len(result["sources"]) > 0
        source = result["sources"][0]
        assert set(source.keys()) == {"source", "chunk_id", "distance"}
        assert source["chunk_id"] is not None
        assert isinstance(source["distance"], float)

    def test_query_never_touches_claude_without_relevant_chunks(
        self, fake_claude_factory, fake_embedding_function, tmp_path
    ):
        empty_dir = tmp_path / "empty_policies"
        empty_dir.mkdir()
        claude = fake_claude_factory("should not be used")
        agent = QualitativeAgent(
            claude_client=claude,
            docs_dir=empty_dir,
            chroma_path=tmp_path / "chroma",
            embedding_function=fake_embedding_function,
        )
        agent.ingest()

        result = agent.query("anything")

        assert result["sources"] == []
        claude.messages.create.assert_not_called()
