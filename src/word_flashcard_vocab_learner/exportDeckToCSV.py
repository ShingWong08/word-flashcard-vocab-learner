import csv
import os

from word_flashcard_vocab_learner.cardDeck import sortByWord
from word_flashcard_vocab_learner.flashCard import Card

DEFAULT_EXPORT_FILE = "vocabulary.csv"

EXPORT_COLUMNS = [
    "Word",
    "Chinese",
    "Definitions",
    "Example",
    "Box",
    "Next review",
    "Correct",
    "Wrong",
    "Added on",
]

# A cell starting with one of these is run as a formula by Excel / Google Sheets.
FORMULA_STARTERS = ("=", "+", "-", "@", "\t", "\r")


def safeCell(value: object) -> object:
    """
    Stop a spreadsheet from treating text as a formula.
    A leading apostrophe is the usual fix; the Word column is left alone so that
    importing the file again still finds the words.

    Parameters:
        Mandatory:
            - value (object): The value of one cell, e.g. a translation, a number or a
              date.
    Returns:
        object: The value with "'" in front when it is text starting with =, +, -, @,
        a tab or a carriage return (see FORMULA_STARTERS). Any other value is returned
        unchanged.
    """

    if isinstance(value, str) and value.startswith(FORMULA_STARTERS):
        return "'" + value

    return value


def cardToRow(card: Card) -> list:
    """
    Turn a card into one CSV row. All definitions go into one cell, numbered and
    separated by " | ", e.g. "1. a pet | 2. a person".

    Parameters:
        Mandatory:
            - card (Card): The card to export.
    Returns:
        list: The cells in the order of EXPORT_COLUMNS: word, Chinese translation,
        definitions, the first example sentence of any definition (or ""), box, next
        review date, right answers, wrong answers and the date the card was added.
        The translation, definitions and example are made safe with safeCell.
    """

    definitions = " | ".join(
        f"{index}. {eachDefinition}"
        for index, eachDefinition in enumerate(card.definitions, start=1)
    )
    firstExample = next(
        (eachExamples[0] for eachExamples in card.examples if eachExamples), ""
    )

    return [
        card.word,
        safeCell(card.translation),
        safeCell(definitions),
        safeCell(firstExample),
        card.box,
        card.nextReview,
        card.correctCount,
        card.wrongCount,
        card.addedOn,
    ]


def exportDeckToCSV(cards: list[Card], path: str) -> int:
    """
    Save the deck as a CSV file that opens in Excel or Google Sheets, or can be imported
    into Quizlet / Anki. The file is UTF-8 with a BOM, so Excel shows Chinese correctly.
    The first row holds the column titles, then one row per card in alphabetical order.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck to export.
            - path (str): The CSV file to write. An existing file is replaced, and a
              missing folder is created.
    Returns:
        int: The number of cards written.
    Raises:
        OSError: When the file cannot be written (e.g. it is open in Excel, or the
        folder is read-only).
    """

    folder = os.path.dirname(path)
    if folder != "":
        os.makedirs(folder, exist_ok=True)

    with open(path, "w", encoding="utf-8-sig", newline="") as csvFile:
        writer = csv.writer(csvFile)
        writer.writerow(EXPORT_COLUMNS)
        writer.writerows(cardToRow(eachCard) for eachCard in sortByWord(cards))

    return len(cards)
