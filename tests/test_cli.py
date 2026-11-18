import requests

import word_flashcard_vocab_learner as app
from word_flashcard_vocab_learner import connectFreeDictionaryAPI as dictionary


def run(monkeypatch, inputs):
    answers = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    app.main()


def test_main_looks_up_word_then_quits(monkeypatch, capsys):
    monkeypatch.setattr(
        dictionary,
        "getWordDefinition",
        lambda word: {"word": word, "definitions": ["a pet"], "translations": ["貓"]},
    )
    run(monkeypatch, ["cat", "q"])

    out = capsys.readouterr().out
    assert 'Definitions of "cat":' in out
    assert "貓" in out
    assert "Goodbye!" in out


def test_main_survives_network_error(monkeypatch, capsys):
    def fail(word):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(dictionary, "getWordDefinition", fail)
    run(monkeypatch, ["cat", "quit"])

    out = capsys.readouterr().out
    assert "Could not reach the dictionary" in out
    assert "Goodbye!" in out
