"""Unit tests for the manager agent's routing logic.

Sub-agents are mocked throughout -- this file tests routing decisions and
the merge/clarify logic, not real qualitative or quantitative behavior.
"""

from unittest.mock import MagicMock

from agents.manager import ManagerAgent


def _manager(claude_text, qual_agent=None, quant_agent=None, fake_claude_factory=None):
    return ManagerAgent(
        claude_client=fake_claude_factory(claude_text),
        qualitative_agent=qual_agent or MagicMock(),
        quantitative_agent=quant_agent or MagicMock(),
    )


class TestRouting:
    def test_qualitative_category_calls_only_qualitative_agent(self, fake_claude_factory):
        qual = MagicMock()
        qual.query.return_value = {"answer": "qual answer"}
        quant = MagicMock()
        manager = _manager("CATEGORY: qualitative\nCLARIFY: NONE", qual, quant, fake_claude_factory)

        result = manager.answer("What is our security policy?")

        assert result["routed_to"] == "qualitative"
        assert result["answer"] == "qual answer"
        qual.query.assert_called_once_with("What is our security policy?")
        quant.query.assert_not_called()

    def test_quantitative_category_calls_only_quantitative_agent(self, fake_claude_factory):
        qual = MagicMock()
        quant = MagicMock()
        quant.query.return_value = {"answer": "quant answer"}
        manager = _manager("CATEGORY: quantitative\nCLARIFY: NONE", qual, quant, fake_claude_factory)

        result = manager.answer("What is total revenue?")

        assert result["routed_to"] == "quantitative"
        assert result["answer"] == "quant answer"
        quant.query.assert_called_once_with("What is total revenue?")
        qual.query.assert_not_called()

    def test_both_category_calls_both_agents_and_merges_with_labels(self, fake_claude_factory):
        qual = MagicMock()
        qual.query.return_value = {"answer": "QUAL PART"}
        quant = MagicMock()
        quant.query.return_value = {"answer": "QUANT PART"}
        manager = _manager("CATEGORY: both\nCLARIFY: NONE", qual, quant, fake_claude_factory)

        result = manager.answer("mixed question")

        assert result["routed_to"] == "both"
        assert "QUAL PART" in result["answer"]
        assert "QUANT PART" in result["answer"]
        assert "qualitative" in result["answer"].lower()
        assert "quantitative" in result["answer"].lower()
        qual.query.assert_called_once()
        quant.query.assert_called_once()
        assert set(result["detail"].keys()) == {"qualitative", "quantitative"}

    def test_ambiguous_category_calls_no_sub_agent_and_returns_clarifying_question(
        self, fake_claude_factory
    ):
        qual = MagicMock()
        quant = MagicMock()
        manager = _manager(
            "CATEGORY: ambiguous\nCLARIFY: Are you asking about policy or data?",
            qual, quant, fake_claude_factory,
        )

        result = manager.answer("tell me about performance")

        assert result["routed_to"] == "ambiguous"
        assert result["answer"] == "Are you asking about policy or data?"
        qual.query.assert_not_called()
        quant.query.assert_not_called()


class TestClassifierFailSafe:
    def test_unparseable_response_falls_back_to_ambiguous(self, fake_claude_factory):
        qual = MagicMock()
        quant = MagicMock()
        manager = _manager(
            "I think this is probably about sales, not sure though",
            qual, quant, fake_claude_factory,
        )

        result = manager.answer("some vague question")

        assert result["routed_to"] == "ambiguous"
        qual.query.assert_not_called()
        quant.query.assert_not_called()

    def test_hallucinated_category_falls_back_to_ambiguous(self, fake_claude_factory):
        qual = MagicMock()
        quant = MagicMock()
        manager = _manager("CATEGORY: financial\nCLARIFY: NONE", qual, quant, fake_claude_factory)

        result = manager.answer("some question")

        assert result["routed_to"] == "ambiguous"
        qual.query.assert_not_called()
        quant.query.assert_not_called()

    def test_ambiguous_without_clarify_line_gets_default_message(self, fake_claude_factory):
        qual = MagicMock()
        quant = MagicMock()
        manager = _manager("CATEGORY: ambiguous", qual, quant, fake_claude_factory)

        result = manager.answer("vague")

        assert result["routed_to"] == "ambiguous"
        assert result["answer"]
