"""One-off diagnostic: prints retrieval distances for known-relevant and
known-irrelevant questions, so the relevance threshold in agents/qualitative.py
can be set from real evidence instead of a guess.

Run once, read the numbers, then delete this file (or keep it -- harmless).
    uv run python data/threshold_diagnostic.py
"""

import chromadb
from chromadb.utils import embedding_functions

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection(
    name="policies", embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

RELEVANT_QUESTIONS = [
    "What is our company's security policy on passwords?",
    "Explain the code review process",
    "How do we handle customer complaints?",
    "What is the remote work policy on equipment?",
]

IRRELEVANT_QUESTIONS = [
    "What is our parental leave policy?",
    "What's the weather like today?",
    "How do I bake a chocolate cake?",
]

for label, questions in [("RELEVANT", RELEVANT_QUESTIONS), ("IRRELEVANT (should be high distance)", IRRELEVANT_QUESTIONS)]:
    print(f"\n=== {label} ===")
    for q in questions:
        results = collection.query(query_texts=[q], n_results=2)
        distances = results["distances"][0]
        sources = [m["source"] for m in results["metadatas"][0]]
        print(f"{q!r}")
        for src, dist in zip(sources, distances):
            print(f"    {dist:.4f}  {src}")
