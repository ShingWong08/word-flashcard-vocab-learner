import json
import os
import shutil
from datetime import date

from word_flashcard_vocab_learner import leitnerScheduler
from word_flashcard_vocab_learner.flashCard import Card


DECK_PATH_ENV = "WORD_FLASHCARD_DECK"


def defaultDeckPath() -> str:

    """
    Return where the deck is saved.
    Uses the WORD_FLASHCARD_DECK environment variable if it is set,
    otherwise ~/.word_flashcard/deck.json, so the same deck is used from any folder.
    """

    customPath = os.environ.get(DECK_PATH_ENV)
    if customPath:
        return customPath

    return os.path.join(os.path.expanduser("~"), ".word_flashcard", "deck.json")


def loadDeck(path: str) -> list[Card]:

    """
    Load all cards from a JSON deck file.
    Returns an empty list if the file does not exist yet.
    Raises ValueError if the file exists but cannot be read as a deck.
    """

    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as deckFile:
            data = json.load(deckFile)

        if not isinstance(data, list):
            raise ValueError("the file does not contain a list of cards")

        cards = []
        for eachCardData in data:
            cards.append(Card.fromDict(eachCardData))

    except (json.JSONDecodeError, TypeError, AttributeError, KeyError, ValueError) as error:
        raise ValueError(f"The deck file '{path}' is damaged: {error}") from error

    return cards


def saveDeck(cards: list[Card], path: str) -> None:

    """
    Save all cards to a JSON deck file.
    The file is written to a temporary file first and then moved into place,
    so the deck is not lost if the program stops halfway through saving.
    """

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    data = []
    for eachCard in cards:
        data.append(eachCard.toDict())

    temporaryPath = path + ".tmp"

    with open(temporaryPath, "w", encoding="utf-8") as deckFile:
        json.dump(data, deckFile, ensure_ascii=False, indent=2)

    .replace(temporaryPath, path)


def backupPath(path: str) -> str:

    """
    Where the backup of a deck file is saved, e.g. "deck.json" -> "deck.backup.json".
    """

    root, extension = os.path.splitext(path)
    if not extension:
        extension = ".json"

    return root + ".backup" + extension


def backupDeck(path: str) -> str | None:

    """
    Copy the deck file to its backup file (replacing the old backup).
    Returns the backup path, or None if there is no deck file yet.
    """

    if not os.path.exists(path):
        return None

    copyPath = backupPath(path)
    shutil.copyfile(path, copyPath)

    return copyPath


def sortByWord(cards: list[Card]) -> list[Card]:

    """
    Return the cards in alphabetical order (ignoring upper / lower case).
    The deck list and the remove screen both use this order, so their numbers match.
    """

    return sorted(cards, key=lambda eachCard: eachCard.word.casefold())


def findCard(cards: list[Card], word: str) -> Card | None:

    """
    Return the card for a word (ignoring upper / lower case), or None if it is not in the deck.
    """

    target = word.strip().casefold()

    for eachCard in cards:
        if eachCard.word.casefold() == target:
            return eachCard

    return None


def addCard(cards: list[Card], card: Card) -> bool:

    """
    Add a card to the deck. Returns False (and adds nothing) if the word is already in the deck.
    """

    if findCard(cards, card.word) is not None:
        return False

    cards.append(card)
    return True


def removeCard(cards: list[Card], word: str) -> bool:

    """
    Remove the card for a word. Returns False if the word is not in the deck.
    """

    card = findCard(cards, word)
    if card is None:
        return False

    cards.remove(card)
    return True


def getDueCards(cards: list[Card], today: date) -> list[Card]:

    """
    Return the cards that are due for review on or before today.
    """

    dueCards = []

    for eachCard in cards:
        if leitnerScheduler.isDue(eachCard, today):
            dueCards.append(eachCard)

    return dueCards


def nextDueDate(cards: list[Card]) -> date | None:

    """
    Return the earliest review date in the deck, or None if the deck is empty.
    """

    if not cards:
        return None

    earliest = cards[0].nextReview

    for eachCard in cards:
        if eachCard.nextReview < earliest:
            earliest = eachCard.nextReview

    return earliest
