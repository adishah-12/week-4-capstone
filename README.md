# Multi-Agent RAG System

Manager agent routes questions to a qualitative (RAG) agent, a quantitative (NL-to-SQL) agent, or both, via CLI or API.

## Setup

```bash
uv sync
uv run python data/seed_db.py
export ANTHROPIC_API_KEY="your-key"   # use a workspace-scoped key, see cli.py comment
```

## Run

```bash
uv run python cli.py                        # CLI
uv run uvicorn api.main:app --reload        # API, docs at /docs
```

## Test

```bash
uv run pytest       
uv run python eval/retrieval_eval.py   
```

## Architecture (or a very terse visual of it at least)

```
CLI (cli.py) / API (api/main.py)
              |
      Manager (agents/manager.py)
      routes: qualitative | quantitative | both | ambiguous
        |                              |
Qualitative (agents/qualitative.py)   Quantitative (agents/quantitative.py)
Chroma + Claude, cited chunks         SQLite (read-only) + Claude, safe SQL
        |                              |
data/policies/*.md                    data/enterprise.db
```

## Where things live

| Requirement | File |
|---|---|
| Manager routing/merge/clarify | `agents/manager.py` |
| Qualitative RAG, chunking, citations, relevance threshold | `agents/qualitative.py` |
| Quantitative NL-to-SQL, safety checks | `agents/quantitative.py` |
| CLI | `cli.py` |
| API routes + schemas | `api/main.py`, `api/schemas.py` |
| Structured logging | `logging_config.py` |
| Seed data | `data/seed_db.py`, `data/policies/*.md` |
| Tests | `tests/` |
| Retrieval eval | `eval/retrieval_eval.py`, `eval/expected_results.json` |


## CI

`.github/workflows/tests.yml` runs `uv sync` + `uv run pytest` on every push and PR. No secrets required - all 61 tests mock the Claude client and use temp SQLite/Chroma fixtures, so nothing needs network access or a real API key.

`eval/retrieval_eval.py` (real embeddings, real Claude calls) is intentionally left out of CI. Running it would require storing `ANTHROPIC_API_KEY` as a repo secret. Run it manually instead: `uv run python eval/retrieval_eval.py`.