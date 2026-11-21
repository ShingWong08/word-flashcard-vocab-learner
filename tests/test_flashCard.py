from datetime import date

from word_flashcard_vocab_learner.flashCard import Card


LOOKUP = {
    "word": "ambiguous",
    "definitions": ["open to more than one meaning", "uncertain"],
    "examples": [["The ending is ambiguous."], []],
}


def test_from_lookup_starts_in_box_one_and_due_today():
    card = Card.fromLookup(LOOKUP, translation="含糊不清")

    assert card.word == "ambiguous"
    assert card.definitions == ["open to more than one meaning", "uncertain"]
    assert card.examples == [["The ending is ambiguous."], []]
    assert card.translation == "含糊不清"
    assert card.box == 1
    assert card.nextReview == date.today().isoformat()
    assert card.timesReviewed() == 0


def test_from_lookup_copies_lists():
    card = Card.fromLookup(LOOKUP)
    card.examples[0].append("changed")

    assert LOOKUP["examples"][0] == ["The ending is ambiguous."]


def test_to_dict_and_from_dict_round_trip():
    card = Card("cat", ["a small animal"], [["The cat sat."]], "貓", 3, "2026-12-01", 4, 1, "2026-11-01")

    assert Card.fromDict(card.toDict()) == card


def test_from_dict_ignores_unknown_keys_and_fills_defaults():
    card = Card.fromDict({"word": "cat", "definitions": ["a pet"], "someFutureField": 1})

    assert card.word == "cat"
    assert card.examples == []
    assert card.box == 1


def test_from_dict_repairs_missing_or_wrong_values():
    card = Card.fromDict({
        "word": "  cat  ",
        "definitions": None,
        "examples": None,
        "translation": 5,
        "box": None,
        "nextReview": "not a date",
        "correctCount": "2",
        "wrongCount": None,
        "addedOn": None,
    })

    assert card.word == "cat"
    assert card.definitions == []
    assert card.examples == []
    assert card.translation == ""
    assert card.box == 1
    assert card.nextReview == date.today().isoformat()
    assert card.correctCount == 2
    assert card.wrongCount == 0
    assert card.addedOn == date.today().isoformat()


def test_from_dict_keeps_the_box_inside_one_to_five():
    assert Card.fromDict({"word": "cat", "definitions": [], "box": 0}).box == 1
    assert Card.fromDict({"word": "cat", "definitions": [], "box": 9}).box == 5


def test_from_dict_needs_a_word():
    import pytest

    with pytest.raises(ValueError, match="no word"):
        Card.fromDict({"definitions": ["a pet"]})
