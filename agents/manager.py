"""Manager agent: classifies each incoming question and routes it to the
qualitative agent, the quantitative agent, both, or asks for clarification.
"""

import logging
import re
from typing import Any

from anthropic import Anthropic

from agents.qualitative import QualitativeAgent
from agents.quantitative import QuantitativeAgent

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

VALID_CATEGORIES = {"qualitative", "quantitative", "both", "ambiguous"}

CLASSIFICATION_SYSTEM_PROMPT = """You route user questions to one of two
backend systems for an enterprise assistant:

- The QUALITATIVE system answers questions about company policy, process,
  and documentation (e.g. security policy, code review process, how
  complaints are handled).
- The QUANTITATIVE system answers questions about company data and numbers
  (e.g. revenue, churn rate, sales figures), by querying a database.

Classify the user's question into exactly one category:
- qualitative: only the qualitative system is needed.
- quantitative: only the quantitative system is needed.
- both: the question genuinely needs information from both systems to be
  answered fully (e.g. it asks for data AND an explanation of policy).
- ambiguous: the question is too vague or unclear to route confidently to
  either system (not simply because it touches both topics).

Respond in EXACTLY this format, two lines, nothing else:
CATEGORY: <qualitative|quantitative|both|ambiguous>
CLARIFY: <a single clarifying question to ask the user, or NONE if category is not ambiguous>"""


class ManagerAgent:
    def __init__(
        self,
        claude_client: Anthropic,
        qualitative_agent: QualitativeAgent,
        quantitative_agent: QuantitativeAgent,
    ) -> None:
        self.claude = claude_client
        self.qualitative_agent = qualitative_agent
        self.quantitative_agent = quantitative_agent

    def _classify(self, question: str) -> tuple[str, str | None]:
        response = self.claude.messages.create(
            model=MODEL,
            max_tokens=200,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        raw_text = "".join(block.text for block in response.content if block.type == "text")

        category_match = re.search(r"CATEGORY:\s*(\w+)", raw_text, re.IGNORECASE)
        clarify_match = re.search(r"CLARIFY:\s*(.+)", raw_text, re.IGNORECASE)

        category = category_match.group(1).lower() if category_match else "ambiguous"
        if category not in VALID_CATEGORIES:
            logger.warning("Classifier returned unrecognized category %r; treating as ambiguous.", category)
            category = "ambiguous"

        clarify_question = clarify_match.group(1).strip() if clarify_match else None
        if clarify_question and clarify_question.upper() == "NONE":
            clarify_question = None

        return category, clarify_question

    def answer(self, question: str) -> dict[str, Any]:
        category, clarify_question = self._classify(question)
        logger.info("Routed question %r to category=%s", question, category)

        if category == "ambiguous":
            return {
                "answer": clarify_question or "Could you clarify what you're asking about?",
                "routed_to": "ambiguous",
                "detail": {},
            }

        if category == "qualitative":
            result = self.qualitative_agent.query(question)
            return {"answer": result["answer"], "routed_to": "qualitative", "detail": result}

        if category == "quantitative":
            result = self.quantitative_agent.query(question)
            return {"answer": result["answer"], "routed_to": "quantitative", "detail": result}

        # category == "both"
        qual_result = self.qualitative_agent.query(question)
        quant_result = self.quantitative_agent.query(question)
        merged_answer = (
            f"**From company policy (qualitative agent):**\n{qual_result['answer']}\n\n"
            f"**From company data (quantitative agent):**\n{quant_result['answer']}"
        )
        return {
            "answer": merged_answer,
            "routed_to": "both",
            "detail": {"qualitative": qual_result, "quantitative": quant_result},
        }
