import csv
import io

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


def test_csv_keeps_text_that_looks_like_a_formula_away_from_the_spreadsheet(tmp_path):
    card = Card("cat", ["a pet"], [["=1+1"]], "=cmd()", nextReview="2026-12-01")
    path = tmp_path / "deck.csv"

    exportDeckToCSV.exportDeckToCSV([card], str(path))

    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    row = rows[1]
    assert row[0] == "cat"        # the word itself is unchanged, so importing again still works
    assert row[1] == "'=cmd()"    # the Chinese translation cannot run as a formula
    assert row[3] == "'=1+1"      # the example cannot run as a formula


def test_normal_text_is_not_changed(tmp_path):
    card = Card("cat", ["a pet"], [["My cat is asleep."]], "貓", nextReview="2026-12-01")
    path = tmp_path / "deck.csv"

    exportDeckToCSV.exportDeckToCSV([card], str(path))

    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    assert rows[1][1] == "貓"
    assert rows[1][3] == "My cat is asleep."
