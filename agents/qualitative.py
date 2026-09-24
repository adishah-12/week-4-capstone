"""Qualitative RAG agent: retrieves policy document chunks from Chroma and
synthesizes a cited answer with Claude.
"""

import logging
import re
from pathlib import Path
from typing import Any

import chromadb
from anthropic import Anthropic
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

DEFAULT_DOCS_DIR = Path(__file__).parent.parent / "data" / "policies"
DEFAULT_CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "policies"

# Chroma cosine distance: 0 = identical, 2 = opposite. Below this, a chunk is
# considered relevant enough to answer from.
#
# Calibrated against real DefaultEmbeddingFunction distances on this corpus
# (see data/threshold_diagnostic.py): every genuinely relevant question's
# top match fell at or below 0.83, every genuinely irrelevant question's top
# match fell at or above 1.17. 1.0 sits in that gap with margin both ways.
DEFAULT_RELEVANCE_THRESHOLD = 1.0

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You answer questions about internal company policy using ONLY
the provided context chunks. Cite which source document each fact comes from
by its filename. If the context does not contain the answer, say so plainly
rather than guessing or using outside knowledge."""


def _chunk_markdown(text: str, source: str) -> list[dict[str, str]]:
    """Splits a markdown doc into chunks on '## ' headers.

    Each chunk keeps its own header as its first line, which gives the
    embedding model a clean topical anchor per chunk.
    """
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]

    # Fold a lone leading H1-only section (title with no body) into the next
    # section instead of emitting a near-empty, low-signal chunk.
    if len(sections) > 1 and not sections[0].lstrip("#").strip().count("\n"):
        title = sections.pop(0)
        sections[0] = f"{title}\n\n{sections[0]}"

    return [
        {"text": section, "source": source, "chunk_id": f"{source}::{i}"}
        for i, section in enumerate(sections)
    ]


class QualitativeAgent:
    def __init__(
        self,
        claude_client: Anthropic,
        docs_dir: Path = DEFAULT_DOCS_DIR,
        chroma_path: Path = DEFAULT_CHROMA_PATH,
        embedding_function: Any | None = None,
        relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    ) -> None:
        self.claude = claude_client
        self.docs_dir = Path(docs_dir)
        self.relevance_threshold = relevance_threshold
        self._embedding_function = (
            embedding_function or embedding_functions.DefaultEmbeddingFunction()
        )
        self._client = chromadb.PersistentClient(path=str(chroma_path))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embedding_function,
        )

    def ingest(self, force: bool = False) -> int:
        """Chunks and embeds every .md file in docs_dir into the collection.

        Idempotent: skips work if the collection is already populated, unless
        force=True (e.g. after editing the source documents).
        """
        if self._collection.count() > 0 and not force:
            logger.info("Collection already populated (%d chunks); skipping ingest.", self._collection.count())
            return self._collection.count()

        if force:
            existing = self._collection.get()
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])

        all_chunks = []
        for md_file in sorted(self.docs_dir.glob("*.md")):
            text = md_file.read_text()
            all_chunks.extend(_chunk_markdown(text, source=md_file.name))

        if not all_chunks:
            logger.warning("No markdown files found in %s", self.docs_dir)
            return 0

        self._collection.add(
            ids=[c["chunk_id"] for c in all_chunks],
            documents=[c["text"] for c in all_chunks],
            metadatas=[{"source": c["source"], "chunk_id": c["chunk_id"]} for c in all_chunks],
        )
        logger.info("Ingested %d chunks from %s", len(all_chunks), self.docs_dir)
        return len(all_chunks)

    def query(self, question: str, n_results: int = 4) -> dict[str, Any]:
        results = self._collection.query(query_texts=[question], n_results=n_results)

        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        relevant = [
            (doc, meta, dist)
            for doc, meta, dist in zip(documents, metadatas, distances)
            if dist <= self.relevance_threshold
        ]

        if not relevant:
            logger.info(
                "No chunks under relevance threshold %.2f for query: %r (best distance: %s)",
                self.relevance_threshold,
                question,
                min(distances) if distances else "n/a",
            )
            return {
                "answer": "I couldn't find anything in the knowledge base that answers this question.",
                "sources": [],
                "detail": {"reason": "below_relevance_threshold"},
            }

        context = "\n\n".join(f"[{meta['source']}]\n{doc}" for doc, meta, _ in relevant)
        response = self.claude.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ],
        )
        answer_text = "".join(block.text for block in response.content if block.type == "text")

        sources = [
            {"source": meta["source"], "chunk_id": meta["chunk_id"], "distance": round(dist, 4)}
            for _, meta, dist in relevant
        ]
        return {"answer": answer_text, "sources": sources, "detail": {"chunks_used": len(relevant)}}
