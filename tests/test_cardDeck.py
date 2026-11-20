import json
import os
from datetime import date

import pytest

from word_flashcard_vocab_learner import cardDeck
from word_flashcard_vocab_learner.flashCard import Card


def makeCard(word, nextReview="2026-11-18", translation=""):
    return Card(word, [f"meaning of {word}"], [[]], translation, nextReview=nextReview)


def test_missing_file_gives_empty_deck(tmp_path):
    assert cardDeck.loadDeck(str(tmp_path / "nothing.json")) == []


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "folder" / "deck.json")
    cards = [makeCard("cat", translation="貓"), makeCard("dog")]

    cardDeck.saveDeck(cards, path)

    assert cardDeck.loadDeck(path) == cards
    assert not os.path.exists(path + ".tmp")


def test_saved_file_keeps_chinese_readable(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat", translation="貓")], path)

    with open(path, encoding="utf-8") as deckFile:
        assert "貓" in deckFile.read()


@pytest.mark.parametrize("content", ["{not json", '{"word": "cat"}', '["cat"]', '[{"definitions": []}]'])
def test_damaged_file_raises_value_error(tmp_path, content):
    path = tmp_path / "deck.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="damaged"):
        cardDeck.loadDeck(str(path))


def test_add_card_refuses_duplicates_ignoring_case():
    cards = []

    assert cardDeck.addCard(cards, makeCard("Cat")) is True
    assert cardDeck.addCard(cards, makeCard("cat")) is False
    assert len(cards) == 1


def test_find_and_remove_card():
    cards = [makeCard("cat"), makeCard("dog")]

    assert cardDeck.findCard(cards, "  DOG ").word == "dog"
    assert cardDeck.findCard(cards, "bird") is None

    assert cardDeck.removeCard(cards, "Cat") is True
    assert cardDeck.removeCard(cards, "cat") is False
    assert [eachCard.word for eachCard in cards] == ["dog"]


def test_get_due_cards():
    cards = [makeCard("past", "2026-11-17"), makeCard("today", "2026-11-18"), makeCard("future", "2026-11-19")]

    dueCards = cardDeck.getDueCards(cards, date(2026, 11, 18))

    assert [eachCard.word for eachCard in dueCards] == ["past", "today"]


def test_backup_deck(tmp_path):
    path = str(tmp_path / "deck.json")

    assert cardDeck.backupDeck(path) is None

    cardDeck.saveDeck([makeCard("cat")], path)
    backup = cardDeck.backupDeck(path)

    assert backup == str(tmp_path / "deck.backup.json")
    assert cardDeck.loadDeck(backup) == cardDeck.loadDeck(path)


def test_sort_by_word_ignores_case():
    cards = [makeCard("banana"), makeCard("Apple"), makeCard("cherry")]
    assert [eachCard.word for eachCard in cardDeck.sortByWord(cards)] == ["Apple", "banana", "cherry"]


def test_next_due_date():
    assert cardDeck.nextDueDate([]) is None
    assert cardDeck.nextDueDate([makeCard("a", "2026-12-05"), makeCard("b", "2026-11-30")]) == "2026-11-30"


def test_default_deck_path_uses_environment_variable(monkeypatch):
    monkeypatch.setenv("WORD_FLASHCARD_DECK", "custom.json")
    assert cardDeck.defaultDeckPath() == "custom.json"


def test_default_deck_path_is_in_home_folder(monkeypatch):
    monkeypatch.delenv("WORD_FLASHCARD_DECK")
    expected = os.path.join(os.path.expanduser("~"), ".word_flashcard", "deck.json")
    assert cardDeck.defaultDeckPath() == expected


def anotherWindowSaves(path, cards):
    # Write the deck the way a second running copy of the program would.
    data = [eachCard.toDict() for eachCard in cards]
    with open(path, "w", encoding="utf-8") as deckFile:
        json.dump(data, deckFile, ensure_ascii=False)


def test_load_deck_that_is_a_folder_gives_a_friendly_error(tmp_path):
    folder = tmp_path / "deck"
    folder.mkdir()

    with pytest.raises(ValueError, match="is a folder, not a deck file"):
        cardDeck.loadDeck(str(folder))


def test_word_added_in_another_window_is_kept(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat")], path)

    cards = cardDeck.loadDeck(path)
    anotherWindowSaves(path, [makeCard("cat"), makeCard("dog")])

    cards.append(makeCard("bird"))
    cardDeck.saveDeck(cards, path)

    assert sorted(eachCard.word for eachCard in cardDeck.loadDeck(path)) == ["bird", "cat", "dog"]


def test_word_removed_here_stays_removed(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat"), makeCard("dog")], path)

    cards = cardDeck.loadDeck(path)
    anotherWindowSaves(path, [makeCard("cat"), makeCard("dog"), makeCard("bird")])

    cards.remove(cardDeck.findCard(cards, "cat"))
    cardDeck.saveDeck(cards, path)

    words = [eachCard.word for eachCard in cardDeck.loadDeck(path)]
    assert "cat" not in words
    assert "bird" in words
    assert "dog" in words


def test_card_changed_here_wins_over_the_file_copy(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat", nextReview="2026-11-18")], path)

    cards = cardDeck.loadDeck(path)
    anotherWindowSaves(path, [makeCard("cat", nextReview="2026-11-18"), makeCard("dog")])

    cardDeck.findCard(cards, "cat").box = 3
    cardDeck.saveDeck(cards, path)

    savedCat = cardDeck.findCard(cardDeck.loadDeck(path), "cat")
    assert savedCat.box == 3


def test_unchanged_card_keeps_the_newer_copy_from_the_file(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat", nextReview="2026-11-18")], path)

    cards = cardDeck.loadDeck(path)
    anotherWindowSaves(path, [makeCard("cat", nextReview="2026-12-01")])

    cardDeck.saveDeck(cards, path)

    assert cardDeck.findCard(cardDeck.loadDeck(path), "cat").nextReview == "2026-12-01"
    # The open window shows the newer copy too.
    assert cardDeck.findCard(cards, "cat").nextReview == "2026-12-01"


def test_saving_after_a_merge_leaves_a_note_for_the_user(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat")], path)

    cards = cardDeck.loadDeck(path)
    anotherWindowSaves(path, [makeCard("cat"), makeCard("dog")])
    cardDeck.saveDeck(cards, path)

    assert cardDeck.takeMergeNote(path) is not None
    assert cardDeck.takeMergeNote(path) is None


def test_unreadable_file_is_copied_before_being_replaced(tmp_path):
    path = str(tmp_path / "deck.json")
    cardDeck.saveDeck([makeCard("cat")], path)

    cards = cardDeck.loadDeck(path)
    with open(path, "w", encoding="utf-8") as deckFile:
        deckFile.write("{not json")

    cards.append(makeCard("dog"))
    cardDeck.saveDeck(cards, path)

    assert os.path.exists(path + ".damaged")
    assert [eachCard.word for eachCard in cardDeck.loadDeck(path)] == ["cat", "dog"]
