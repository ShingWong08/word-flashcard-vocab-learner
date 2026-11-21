import csv
import os

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


def safeCell(value) -> object:

    """
    Stop a spreadsheet from treating text as a formula.
    A leading apostrophe is the usual fix; the Word column is left alone so that
    importing the file again still finds the words.
    """

    if isinstance(value, str) and value.startswith(FORMULA_STARTERS):
        return "'" + value

    return value


def cardToRow(card: Card) -> list:

    """
    Turn a card into one CSV row. All definitions go into one cell, numbered and separated by " | ".
    """

    numberedDefinitions = []
    for index, eachDefinition in enumerate(card.definitions, start=1):
        numberedDefinitions.append(f"{index}. {eachDefinition}")

    firstExample = ""
    for eachExampleList in card.examples:
        if eachExampleList and len(eachExampleList) > 0:
            firstExample = eachExampleList[0]
            break

    return [
        card.word,
        safeCell(card.translation),
        safeCell(" | ".join(numberedDefinitions)),
        safeCell(firstExample),
        card.box,
        card.nextReview,
        card.correctCount,
        card.wrongCount,
        card.addedOn,
    ]


def exportDeckToCSV(cards: list[Card], path: str) -> int:

    """
    Save the deck as a CSV file that opens in Excel or Google Sheets, or can be imported into
    Quizlet / Anki. The file is UTF-8 with a BOM, so Excel shows Chinese correctly.
    Returns the number of cards written.
    """

    folder = os.path.dirname(path)
    if folder != "":
        os.makedirs(folder, exist_ok=True)

    sortedCards = sorted(cards, key=lambda eachCard: eachCard.word.casefold())

    with open(path, "w", encoding="utf-8-sig", newline="") as csvFile:
        writer = csv.writer(csvFile)
        writer.writerow(EXPORT_COLUMNS)

        for eachCard in sortedCards:
            writer.writerow(cardToRow(eachCard))

    return len(sortedCards)
