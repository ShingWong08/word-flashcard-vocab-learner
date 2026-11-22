import pytest

from word_flashcard_vocab_learner import userInput


def testAskTrimsSpacesAndByteOrderMark(typeAnswers):
    typeAnswers(["﻿  1  "])
    assert userInput.ask("Choose: ") == "1"


def testAskReturnsNoneOnCtrlC(monkeypatch):
    def pressCtrlC(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", pressCtrlC)
    assert userInput.ask("Choose: ") is None


@pytest.mark.parametrize(
    "answer, expected", [("y", True), ("YES", True), ("n", False), ("q", None)]
)
def testAskYesNo(typeAnswers, answer, expected):
    typeAnswers([answer])
    assert userInput.askYesNo("Continue? ") is expected


def testAskYesNoUsesDefaultAndRepeatsInvalidAnswers(typeAnswers):
    prompts = typeAnswers(["maybe", ""])
    assert userInput.askYesNo("Continue? (y/N) ", default=False) is False
    assert len(prompts) == 2


def testAskYesNoWithoutDefaultRepeatsEmptyAnswersQuietly(typeAnswers, capsys):
    prompts = typeAnswers(["", "", "", "y"])

    assert userInput.askYesNo("Did you remember it? (y/n): ") is True
    assert len(prompts) == 4
    assert "Please answer y or n." not in capsys.readouterr().out


def testIsQuit():
    assert userInput.isQuit(None) is True
    assert userInput.isQuit("Quit") is True
    assert userInput.isQuit("cat") is False
