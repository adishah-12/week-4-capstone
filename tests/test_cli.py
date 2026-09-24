"""Tests for the CLI's REPL loop.

run_repl() takes input_fn/output_fn as parameters specifically so it can be
tested here without a real terminal, a real Anthropic client, or any network.
"""

from unittest.mock import MagicMock

from cli import EXIT_COMMANDS, run_repl


def _scripted_input(*responses):
    it = iter(responses)
    return lambda prompt: next(it)


class TestRunRepl:
    def test_prints_answer_then_exits_on_exit_command(self):
        manager = MagicMock()
        manager.answer.return_value = {"answer": "Test answer", "routed_to": "qualitative"}
        outputs = []

        run_repl(manager, input_fn=_scripted_input("a question", "exit"), output_fn=outputs.append)

        assert any("Test answer" in line for line in outputs)
        assert outputs[-1] == "Exiting."
        manager.answer.assert_called_once_with("a question")

    def test_quit_is_also_a_valid_exit_command(self):
        assert "quit" in EXIT_COMMANDS
        assert "exit" in EXIT_COMMANDS
        manager = MagicMock()
        outputs = []
        run_repl(manager, input_fn=_scripted_input("quit"), output_fn=outputs.append)
        assert outputs[-1] == "Exiting."
        manager.answer.assert_not_called()

    def test_blank_input_is_skipped_without_calling_manager(self):
        manager = MagicMock()
        run_repl(manager, input_fn=_scripted_input("", "   ", "exit"), output_fn=lambda x: None)
        manager.answer.assert_not_called()

    def test_eof_exits_cleanly(self):
        manager = MagicMock()
        outputs = []

        def raise_eof(prompt):
            raise EOFError()

        run_repl(manager, input_fn=raise_eof, output_fn=outputs.append)
        assert "Exiting." in outputs[-1]

    def test_keyboard_interrupt_exits_cleanly(self):
        manager = MagicMock()
        outputs = []

        def raise_kb(prompt):
            raise KeyboardInterrupt()

        run_repl(manager, input_fn=raise_kb, output_fn=outputs.append)
        assert "Exiting." in outputs[-1]

    def test_exception_during_answer_is_reported_and_repl_continues(self):
        manager = MagicMock()
        manager.answer.side_effect = [
            RuntimeError("API error"),
            {"answer": "recovered", "routed_to": "qualitative"},
        ]
        outputs = []

        run_repl(
            manager,
            input_fn=_scripted_input("bad question", "good question", "exit"),
            output_fn=outputs.append,
        )

        assert any("something went wrong" in line.lower() for line in outputs)
        assert any("recovered" in line for line in outputs)
        assert manager.answer.call_count == 2

    def test_routed_to_label_is_shown_for_each_answer(self):
        manager = MagicMock()
        manager.answer.return_value = {"answer": "x", "routed_to": "both"}
        outputs = []
        run_repl(manager, input_fn=_scripted_input("q", "exit"), output_fn=outputs.append)
        assert any("both" in line for line in outputs)
