import json
import os
import shutil
from datetime import date

from word_flashcard_vocab_learner import leitnerScheduler
from word_flashcard_vocab_learner.flashCard import Card


DECK_PATH_ENV = "WORD_FLASHCARD_DECK"

# Card data last read from or written to each deck file, keyed by _deckKey(path).
# saveDeck uses it to see what changed here and what changed in another window.
_knownDecks: dict[str, list[dict]] = {}

# Note for the user, set by saveDeck when it had to merge in changes made elsewhere.
_mergeNotes: dict[str, str] = {}

# Size and modification time of each deck file as this program last saw it, keyed by _deckKey(path).
# When they are unchanged, saveDeck does not have to read the whole file again to look for another window.
_fileStamps: dict[str, tuple[int, int]] = {}


class DeckSaveError(Exception):

    """
    Raised when the deck file cannot be written, e.g. the folder is read-only or the disk is full.
    The message is meant for the user; the cards in memory are not lost.
    """


def defaultDeckPath() -> str:

    """
    Return where the deck is saved.
    Uses the WORD_FLASHCARD_DECK environment variable if it is set,
    otherwise ~/.word_flashcard/deck.json, so the same deck is used from any folder.
    """

    customPath = os.environ.get(DECK_PATH_ENV)
    if customPath:
        return os.path.expanduser(customPath)

    return os.path.join(os.path.expanduser("~"), ".word_flashcard", "deck.json")


def loadDeck(path: str) -> list[Card]:

    """
    Load all cards from a JSON deck file.
    Returns an empty list if the file does not exist/ file is completely empty.
    Raises ValueError if the file exists but cannot be read as a deck.
    """

    data = _readDeckData(path)

    try:
        cards = []
        for eachCardData in data:
            cards.append(Card.fromDict(eachCardData))

    except (TypeError, AttributeError, KeyError, ValueError) as error:
        raise ValueError(f"The deck file '{path}' is damaged: {error}") from error

    _knownDecks[_deckKey(path)] = data

    return cards


def saveDeck(cards: list[Card], path: str) -> None:

    """
    Save all cards to a JSON deck file.
    The file is written to a temporary file first and then moved into place,
    so the deck is not lost if the program stops halfway through saving.

    If another window changed the deck file since this one read it, both sets of
    changes are kept (see mergeDecks), so one window never silently overwrites
    the words added in the other.
    """

    data = []
    for eachCard in cards:
        data.append(eachCard.toDict())

    key = _deckKey(path)
    knownData = _knownDecks.get(key)
    mergedElsewhere = False
    stamp = _fileStamp(path)

    # Read the file again only when another window may have changed it since we last read or wrote it.
    unchangedSinceLastTime = stamp is not None and stamp == _fileStamps.get(key)

    if knownData is not None and stamp is not None and not unchangedSinceLastTime:
        try:
            fileData = _readDeckData(path)
        except ValueError:
            # The file was replaced by something this program cannot read.
            # Keep a copy of it before it gets overwritten.
            try:
                shutil.copyfile(path, path + ".damaged")
            except OSError:
                pass
        else:
            if fileData != knownData:
                data = mergeDecks(knownData, data, fileData)
                _mergeNotes[key] = "Another window changed the deck, so both changes were kept."
                mergedElsewhere = True

    _writeDeckData(data, path)

    if mergedElsewhere:
        _applyMergedData(cards, data)

    _knownDecks[key] = data
    _fileStamps[key] = _fileStamp(path)


def takeMergeNote(path: str) -> str | None:

    """
    Return (and clear) the note left by the last save if it had to merge in
    changes made by another window, or None when no merge happened.
    """

    return _mergeNotes.pop(_deckKey(path), None)


def mergeDecks(knownData: list[dict], newData: list[dict], fileData: list[dict]) -> list[dict]:

    """
    Combine the deck this window has (newData) with the deck another window saved
    meanwhile (fileData), using what this window last read (knownData) to see what changed.
    Returns the merged list of card dicts.

    Rules:
        - a card changed here wins over the older copy in the file;
        - a card this window did not change keeps the newer copy from the file;
        - a word added in either window is kept;
        - a word removed here stays removed.
    """

    knownByWord = {}
    for eachCardData in knownData:
        knownByWord[_cardKey(eachCardData)] = eachCardData

    newByWord = {}
    for eachCardData in newData:
        newByWord[_cardKey(eachCardData)] = eachCardData

    fileByWord = {}
    for eachCardData in fileData:
        fileByWord[_cardKey(eachCardData)] = eachCardData

    merged = []

    for word, newCard in newByWord.items():
        fileCard = fileByWord.get(word)
        knownCard = knownByWord.get(word)

        if fileCard is None:
            # Not in the file: either added here, or another window deleted it.
            if knownCard is None or newCard != knownCard:
                merged.append(newCard)
            continue

        if knownCard is None or newCard != knownCard:
            merged.append(newCard)
        else:
            merged.append(fileCard)

    for word, fileCard in fileByWord.items():
        if word in newByWord:
            continue
        if word in knownByWord:
            # Removed in this window: keep it removed.
            continue
        merged.append(fileCard)

    return merged


def _applyMergedData(cards: list[Card], mergedData: list[dict]) -> None:

    """
    Bring the caller's card list up to date with the merged deck, so the next save
    does not put the old values back. Cards already in the list are updated in place
    (a review session may still hold those objects), cards added by another window
    are appended, and cards another window deleted are dropped.
    """

    mergedKeys = []
    for eachCardData in mergedData:
        mergedKeys.append(_cardKey(eachCardData))

    for eachCardData in mergedData:
        newCard = Card.fromDict(eachCardData)
        existingCard = findCard(cards, newCard.word)

        if existingCard is None:
            cards.append(newCard)
        else:
            existingCard.__dict__.update(newCard.__dict__)

    for index in range(len(cards) - 1, -1, -1):
        if _cardKey(cards[index].toDict()) not in mergedKeys:
            del cards[index]


def _fileStamp(path: str) -> tuple[int, int] | None:

    """
    Return (modification time, size) of a deck file, or None when it does not exist.
    Used to skip re-reading a deck that this program itself last wrote.
    """

    if not os.path.exists(path):
        return None

    try:
        fileStat = os.stat(path)
    except OSError:
        return None

    return (fileStat.st_mtime_ns, fileStat.st_size)


def _readDeckData(path: str) -> list[dict]:

    """
    Read the list of card dicts from a deck file, without building Card objects.
    Returns an empty list if the file does not exist or is empty.
    Raises ValueError with a message the user can act on if the path cannot be used as a deck.
    """

    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as deckFile:
            content = deckFile.read().strip()

    except IsADirectoryError:
        raise ValueError(
            f"'{path}' is a folder, not a deck file. "
            "Point WORD_FLASHCARD_DECK at a .json file, for example ~/.word_flashcard/deck.json."
        ) from None

    except PermissionError:
        raise ValueError(f"The deck file '{path}' cannot be read: permission denied.") from None

    except UnicodeDecodeError:
        raise ValueError(f"The deck file '{path}' is damaged: it is not UTF-8 text.") from None

    except OSError as error:
        raise ValueError(f"The deck file '{path}' cannot be read: {error}") from error

    _fileStamps[_deckKey(path)] = _fileStamp(path)

    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(f"The deck file '{path}' is damaged: {error}") from error

    if not isinstance(data, list):
        raise ValueError(f"The deck file '{path}' is damaged: the file does not contain a list of cards")

    return data


def _writeDeckData(data: list[dict], path: str) -> None:

    """
    Write the card dicts to the deck file: temporary file first, then move it into place.
    """

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    temporaryPath = path + ".tmp"

    try:
        with open(temporaryPath, "w", encoding="utf-8") as deckFile:
            json.dump(data, deckFile, ensure_ascii=False, indent=2)

        os.replace(temporaryPath, path)

    except OSError as error:
        if os.path.exists(temporaryPath):
            try:
                os.remove(temporaryPath)
            except OSError:
                pass

        reason = error.strerror or str(error)
        raise DeckSaveError(f"The deck file '{path}' cannot be written: {reason.lower() if reason else error}.") from error



def _deckKey(path: str) -> str:

    """
    The key used to remember a deck file: the same file always gets the same key.
    """

    return os.path.abspath(os.path.expanduser(path))


def _cardKey(cardData: dict) -> str:

    """
    The word a card is filed under, matching how findCard compares words.
    """

    word = cardData.get("word")

    if not isinstance(word, str):
        return ""

    return word.strip().casefold()


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
