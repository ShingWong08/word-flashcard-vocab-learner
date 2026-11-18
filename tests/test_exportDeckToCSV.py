import csv

from word_flashcard_vocab_learner import exportDeckToCSV, importVocabulary
from word_flashcard_vocab_learner.flashCard import Card


def test_export_deck_to_csv(tmp_path):
    cards = [
        Card("dog", ["a pet", "a person"], [[], ["You lucky dog!"]], "狗", 2, "2026-11-20", 1, 0, "2026-11-01"),
        Card("cat", ["a small animal"], [["The cat sat."]], "貓"),
    ]
    path = tmp_path / "out" / "deck.csv"

    count = exportDeckToCSV.exportDeckToCSV(cards, str(path))

    assert count == 2
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")

    with open(path, encoding="utf-8-sig", newline="") as csvFile:
        rows = list(csv.reader(csvFile))

    assert rows[0] == exportDeckToCSV.EXPORT_COLUMNS
    assert [eachRow[0] for eachRow in rows[1:]] == ["cat", "dog"]
    assert rows[2][1:5] == ["狗", "1. a pet | 2. a person", "You lucky dog!", "2"]


def test_exported_csv_can_be_imported_again(tmp_path):
    path = tmp_path / "deck.csv"
    exportDeckToCSV.exportDeckToCSV([Card("ambiguous", ["unclear"]), Card("ice cream", ["a frozen dessert"])], str(path))

    text = importVocabulary.readTextFromFile(str(path))

    assert importVocabulary.extractWords(text) == ["ambiguous", "ice cream"]
