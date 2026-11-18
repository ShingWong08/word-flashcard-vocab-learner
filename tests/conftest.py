import pytest


@pytest.fixture(autouse=True)
def isolateEnvironment(monkeypatch, tmp_path):

    """
    Keep every test away from real API keys, the user's real deck and the project's cache folders.
    """

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("WORD_FLASHCARD_DECK", str(tmp_path / "deck.json"))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def typeAnswers(monkeypatch):

    """
    Return a function that feeds answers to input(), one per prompt.
    The prompts that were shown are collected in the returned list.
    """

    prompts = []

    def setAnswers(answers):
        remaining = iter(answers)

        def fakeInput(prompt=""):
            prompts.append(prompt)
            return next(remaining)

        monkeypatch.setattr("builtins.input", fakeInput)
        return prompts

    return setAnswers
