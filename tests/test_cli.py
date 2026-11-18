from datetime import date

import requests

import word_flashcard_vocab_learner as app
from word_flashcard_vocab_learner import cardDeck, genAITutor
from word_flashcard_vocab_learner import connectFreeDictionaryAPI as dictionary
from word_flashcard_vocab_learner.flashCard import Card


CAT_LOOKUP = {"word": "cat", "definitions": ["a pet"], "examples": [["My cat is asleep."]]}


def fakeLookup(monkeypatch):
    monkeypatch.setattr(dictionary, "getWordDefinition", lambda word: CAT_LOOKUP)


def deckPath(tmp_path):
    return str(tmp_path / "deck.json")


def saveCat(tmp_path, nextReview=None):
    if nextReview is None:
        nextReview = date.today().isoformat()

    card = Card("cat", ["a pet"], [["My cat is asleep."]], "貓", nextReview=nextReview)
    cardDeck.saveDeck([card], deckPath(tmp_path))


def test_look_up_word_and_add_it_to_deck(monkeypatch, capsys, tmp_path, typeAnswers):
    fakeLookup(monkeypatch)
    typeAnswers(["1", "cat", "y", "", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert 'Definitions of "cat":' in out
    assert "  1. a pet" in out
    assert "     > My cat is asleep." in out
    assert "Chinese" not in out
    assert 'Added "cat" to your deck (1 word).' in out
    assert "Goodbye!" in out

    savedCards = cardDeck.loadDeck(deckPath(tmp_path))
    assert [eachCard.word for eachCard in savedCards] == ["cat"]


def test_translation_is_shown_and_saved_when_ai_is_set_up(monkeypatch, capsys, tmp_path, typeAnswers):
    fakeLookup(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setattr(genAITutor, "translateWord", lambda word, definition: "貓")
    typeAnswers(["1", "cat", "y", "", "q"])

    app.main(deckPath(tmp_path))

    assert "Chinese: 貓" in capsys.readouterr().out
    assert cardDeck.loadDeck(deckPath(tmp_path))[0].translation == "貓"


def test_word_already_in_deck_is_not_offered_again(monkeypatch, capsys, tmp_path, typeAnswers):
    fakeLookup(monkeypatch)
    saveCat(tmp_path)
    typeAnswers(["1", "cat", "", "q"])

    app.main(deckPath(tmp_path))

    assert '"cat" is already in your deck (box 1).' in capsys.readouterr().out


def test_main_survives_network_error(monkeypatch, capsys, tmp_path, typeAnswers):
    def fail(word):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(dictionary, "getWordDefinition", fail)
    typeAnswers(["1", "cat", "", "quit"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Could not reach the dictionary" in out
    assert "Goodbye!" in out


def test_review_due_card_in_spelling_mode(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["2", "2", "cat", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Due today: 1 card." in out
    assert "Card 1 of 1" in out
    assert "Correct!" in out
    assert "Session finished" in out
    assert "  Reviewed  1 card" in out
    assert "  Score     100%" in out

    savedCard = cardDeck.loadDeck(deckPath(tmp_path))[0]
    assert savedCard.box == 2
    assert savedCard.correctCount == 1


def test_no_due_cards_offers_practice(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path, nextReview="2999-01-01")
    typeAnswers(["2", "n", "q"])

    app.main(deckPath(tmp_path))

    assert "No cards are due today. Next review: 2999-01-01." in capsys.readouterr().out


def test_review_empty_deck(capsys, tmp_path, typeAnswers):
    typeAnswers(["2", "q"])

    app.main(deckPath(tmp_path))

    assert "Your deck is empty" in capsys.readouterr().out


def test_view_deck(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["4", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Your deck: 1 word, 1 due today" in out
    assert "cat" in out
    assert "貓" in out


def test_remove_word(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["7", "CAT", "y", "", "q"])

    app.main(deckPath(tmp_path))

    assert "Removed 1 word." in capsys.readouterr().out
    assert cardDeck.loadDeck(deckPath(tmp_path)) == []


def test_damaged_deck_is_not_overwritten(capsys, tmp_path, typeAnswers):
    path = tmp_path / "deck.json"
    path.write_text("{broken", encoding="utf-8")
    typeAnswers([])

    app.main(str(path))

    assert "damaged" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == "{broken"


def test_unknown_menu_choice(capsys, tmp_path, typeAnswers):
    typeAnswers(["9", "q"])

    app.main(deckPath(tmp_path))

    assert "Please choose 1 - 7, c or q." in capsys.readouterr().out


def test_main_uses_default_deck_path(capsys, tmp_path, typeAnswers):
    typeAnswers(["q"])

    app.main()

    assert "Your deck has 0 words" in capsys.readouterr().out


def test_menu_shows_due_count(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["q"])

    app.main(deckPath(tmp_path))

    assert "2. Review cards  (1 due)" in capsys.readouterr().out


def test_clear_screen_command(monkeypatch, tmp_path, typeAnswers):
    cleared = []
    monkeypatch.setattr(app.terminalDisplay, "clearScreen", lambda: cleared.append(1))
    typeAnswers(["clear", "c", "q"])

    app.main(deckPath(tmp_path))

    assert len(cleared) == 2


def test_import_words_from_text_file(monkeypatch, capsys, tmp_path, typeAnswers):
    wordList = tmp_path / "words.txt"
    wordList.write_text("1. ambiguous - unclear\n2. cat - 貓\n3. qwzx\n", encoding="utf-8")

    def fakeGetWordDefinition(word):
        if word == "qwzx":
            return {"word": word, "definitions": [], "examples": []}
        return {"word": word, "definitions": [f"meaning of {word}"], "examples": [[]]}

    monkeypatch.setattr(dictionary, "getWordDefinition", fakeGetWordDefinition)
    typeAnswers(["3", f'"{wordList}"', "", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Words found in words.txt" in out
    assert "1. ambiguous" in out
    assert "skipped: not found in the dictionary" in out
    assert "Added 2, skipped 1." in out
    assert [eachCard.word for eachCard in cardDeck.loadDeck(deckPath(tmp_path))] == ["ambiguous", "cat"]


def test_progress_screen(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["5", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Your progress" in out
    assert "Words in deck     1" in out


def test_export_deck(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    exportPath = tmp_path / "my words"
    typeAnswers(["6", str(exportPath), "q"])

    app.main(deckPath(tmp_path))

    assert "Exported 1 word to" in capsys.readouterr().out
    assert "貓" in (tmp_path / "my words.csv").read_text(encoding="utf-8-sig")


def test_export_asks_before_replacing(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    existing = tmp_path / "old.csv"
    existing.write_text("keep me", encoding="utf-8")
    typeAnswers(["6", str(existing), "n", "q"])

    app.main(deckPath(tmp_path))

    assert existing.read_text(encoding="utf-8") == "keep me"
