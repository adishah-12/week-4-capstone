"""CLI entry point: a REPL loop that takes a question, prints the routed
agent's answer, and exits cleanly on 'exit'/'quit' or Ctrl-C.

    uv run python cli.py
"""

import logging
import sys

from anthropic import Anthropic

from agents.manager import ManagerAgent
from agents.qualitative import QualitativeAgent
from agents.quantitative import QuantitativeAgent
from logging_config import setup_logging

logger = logging.getLogger(__name__)

EXIT_COMMANDS = {"exit", "quit"}


def build_manager() -> ManagerAgent:
    claude_client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    qualitative_agent = QualitativeAgent(claude_client=claude_client)
    qualitative_agent.ingest()  # no-op if already ingested
    quantitative_agent = QuantitativeAgent(claude_client=claude_client)
    return ManagerAgent(
        claude_client=claude_client,
        qualitative_agent=qualitative_agent,
        quantitative_agent=quantitative_agent,
    )


def run_repl(manager: ManagerAgent, input_fn=input, output_fn=print) -> None:
    """The REPL loop itself, with input/output injected so it can be tested
    without a real terminal or a real Anthropic client.
    """
    output_fn("Multi-agent RAG system. Type a question, or 'exit' to quit.")
    while True:
        try:
            question = input_fn("> ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("\nExiting.")
            return

        if not question:
            continue
        if question.lower() in EXIT_COMMANDS:
            output_fn("Exiting.")
            return

        try:
            result = manager.answer(question)
        except Exception as e:
            logger.exception("Unhandled error answering question: %r", question)
            output_fn(f"Something went wrong answering that: {e}")
            continue

        output_fn(f"[routed to: {result['routed_to']}]")
        output_fn(result["answer"])
        output_fn("")


def main() -> None:
    setup_logging()
    try:
        manager = build_manager()
    except Exception:
        logger.exception("Failed to initialize agents")
        print(
            "Failed to start. See app.log (or the output above) for the "
            "underlying error -- common causes: ANTHROPIC_API_KEY not set, "
            "data/enterprise.db missing (run: uv run python data/seed_db.py), "
            "or no network access to download the embedding model on first run.",
            file=sys.stderr,
        )
        sys.exit(1)

    run_repl(manager)


if __name__ == "__main__":
    main()
