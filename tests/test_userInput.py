import pytest

from word_flashcard_vocab_learner import userInput


def test_ask_trims_spaces_and_byte_order_mark(typeAnswers):
    typeAnswers(["﻿  1  "])
    assert userInput.ask("Choose: ") == "1"


def test_ask_returns_none_on_ctrl_c(monkeypatch):
    def pressCtrlC(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", pressCtrlC)
    assert userInput.ask("Choose: ") is None


@pytest.mark.parametrize("answer, expected", [("y", True), ("YES", True), ("n", False), ("q", None)])
def test_ask_yes_no(typeAnswers, answer, expected):
    typeAnswers([answer])
    assert userInput.askYesNo("Continue? ") is expected


def test_ask_yes_no_uses_default_and_repeats_invalid_answers(typeAnswers):
    prompts = typeAnswers(["maybe", ""])
    assert userInput.askYesNo("Continue? (y/N) ", default=False) is False
    assert len(prompts) == 2


def test_ask_yes_no_without_default_repeats_empty_answers_quietly(typeAnswers, capsys):
    prompts = typeAnswers(["", "", "", "y"])

    assert userInput.askYesNo("Did you remember it? (y/n): ") is True
    assert len(prompts) == 4
    assert "Please answer y or n." not in capsys.readouterr().out


def test_is_quit():
    assert userInput.isQuit(None) is True
    assert userInput.isQuit("Quit") is True
    assert userInput.isQuit("cat") is False
