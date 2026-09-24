"""Standalone retrieval evaluation for the qualitative agent.

Runs a fixed set of hand-labeled questions (eval/expected_results.json)
against the real Chroma collection and checks:
  - for questions with an expected source: that source is actually retrieved
    (i.e. the agent doesn't skip it as below-threshold, and it appears among
    the returned sources) AND the agent answers rather than saying "not found".
  - for deliberately out-of-knowledge-base questions: the agent correctly
    reports "not found" rather than fabricating an answer.

This is deliberately separate from the pytest suite: it exercises real
embeddings and real retrieval quality, which is a different kind of check
than the mocked unit/integration tests.

    uv run python eval/retrieval_eval.py
"""

import json
import sys
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.qualitative import QualitativeAgent  # noqa: E402

EXPECTED_RESULTS_PATH = Path(__file__).parent / "expected_results.json"


def run_eval() -> bool:
    with open(EXPECTED_RESULTS_PATH) as f:
        cases = json.load(f)

    claude_client = Anthropic()
    agent = QualitativeAgent(claude_client=claude_client)
    agent.ingest()

    passed = 0
    failed = 0

    for case in cases:
        question = case["question"]
        expected_source = case["expected_source"]
        should_answer = case["should_answer"]

        result = agent.query(question)
        retrieved_sources = {s["source"] for s in result["sources"]}
        did_answer = len(result["sources"]) > 0

        if should_answer:
            ok = did_answer and expected_source in retrieved_sources
            detail = f"expected {expected_source!r} in {retrieved_sources or '{}'}"
        else:
            ok = not did_answer
            detail = f"expected no answer; got sources={retrieved_sources or '{}'}"

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {question!r} -- {detail}")

    print(f"\n{passed}/{len(cases)} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_eval()
    sys.exit(0 if success else 1)
