import json
import os
import shutil
from datetime import date

from word_flashcard_vocab_learner import leitnerScheduler
from word_flashcard_vocab_learner.flashCard import Card

DECK_PATH_ENV = "WORD_FLASHCARD_DECK"
MERGE_NOTE = "Another window changed the deck, so both changes were kept."

# Card data last read from or written to each deck file, keyed by _deckKey(path).
# saveDeck uses it to see what changed here and what changed in another window.
_knownDecks: dict[str, list[dict]] = {}

# Note for the user, set by saveDeck when it had to merge in changes made elsewhere.
_mergeNotes: dict[str, str] = {}

# Size and modification time of each deck file as this program last saw it, keyed by
# _deckKey(path).
# When they are unchanged, saveDeck does not have to read the whole file again to look
# for another window.
_fileStamps: dict[str, tuple[int, int] | None] = {}


class DeckSaveError(Exception):
    """
    Raised when the deck file cannot be written, e.g. the folder is read-only or the
    disk is full.
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
        # normpath turns "~/x/deck.json" into C:\Users\...\x\deck.json on Windows,
        # instead of a path with both kinds of slash.
        return os.path.normpath(os.path.expanduser(customPath))

    return os.path.join(os.path.expanduser("~"), ".word_flashcard", "deck.json")


def loadDeck(path: str) -> list[Card]:
    """
    Load all cards from a JSON deck file.
    Returns an empty list if the file does not exist/ file is completely empty.
    Raises ValueError if the file exists but cannot be read as a deck.
    """

    cards = _cardsFromData(_readDeckData(path), path)

    # Keep the repaired card data, so the next save writes back what the screens show
    # and does not compare against a hand-edited entry for ever.
    _knownDecks[_deckKey(path)] = [eachCard.toDict() for eachCard in cards]

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

    data = [eachCard.toDict() for eachCard in cards]
    key = _deckKey(path)
    knownData = _knownDecks.get(key)
    stamp = _fileStamp(path)
    merged = False

    # Read the file again only when another window may have changed it since we last
    # read or wrote it.
    if knownData is not None and stamp is not None and stamp != _fileStamps.get(key):
        try:
            fileData = _normaliseDeckData(_readDeckData(path), path)
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
                _mergeNotes[key] = MERGE_NOTE
                merged = True

    _writeDeckData(data, path)

    if merged:
        _applyMergedData(cards, data)

    _knownDecks[key] = data
    _fileStamps[key] = _fileStamp(path)


def takeMergeNote(path: str) -> str | None:
    """
    Return (and clear) the note left by the last save if it had to merge in
    changes made by another window, or None when no merge happened.
    """

    return _mergeNotes.pop(_deckKey(path), None)


def mergeDecks(
    knownData: list[dict], newData: list[dict], fileData: list[dict]
) -> list[dict]:
    """
    Combine the deck this window has (newData) with the deck another window saved
    meanwhile (fileData), using what this window last read (knownData) to see what
    changed.
    Returns the merged list of card dicts.

    Rules:
        - a card changed here wins over the older copy in the file;
        - a card this window did not change keeps the newer copy from the file;
        - a word added in either window is kept;
        - a word removed here stays removed.
    """

    knownByWord = {_cardKey(each): each for each in knownData}
    newByWord = {_cardKey(each): each for each in newData}
    fileByWord = {_cardKey(each): each for each in fileData}

    merged = []

    for word, newCard in newByWord.items():
        knownCard = knownByWord.get(word)

        if knownCard is None or newCard != knownCard:
            # Added or changed here.
            merged.append(newCard)
        elif word in fileByWord:
            # Not changed here: keep the newer copy from the file.
            merged.append(fileByWord[word])
        # Otherwise another window deleted it.

    # Words added in another window. A word removed here (known, but no longer here)
    # stays removed.
    merged.extend(
        fileCard
        for word, fileCard in fileByWord.items()
        if word not in newByWord and word not in knownByWord
    )

    return merged


def _applyMergedData(cards: list[Card], mergedData: list[dict]) -> None:
    """
    Bring the caller's card list up to date with the merged deck, so the next save
    does not put the old values back. Cards already in the list are updated in place
    (a review session may still hold those objects), cards added by another window
    are appended, and cards another window deleted are dropped.
    """

    # Same lookup as findCard (the first card with that word wins), without searching
    # the list each time.
    cardsByWord = {}
    for eachCard in cards:
        cardsByWord.setdefault(eachCard.word.casefold(), eachCard)

    for eachCardData in mergedData:
        newCard = Card.fromDict(eachCardData)
        existingCard = cardsByWord.setdefault(newCard.word.casefold(), newCard)

        if existingCard is newCard:
            cards.append(newCard)
        else:
            existingCard.__dict__.update(newCard.__dict__)

    mergedKeys = {_cardKey(each) for each in mergedData}
    cards[:] = [eachCard for eachCard in cards if _wordKey(eachCard.word) in mergedKeys]


def _fileStamp(path: str) -> tuple[int, int] | None:
    """
    Return (modification time, size) of a deck file, or None when it does not exist.
    Used to skip re-reading a deck that this program itself last wrote.
    """

    try:
        fileStat = os.stat(path)
    except (OSError, ValueError):
        return None

    return (fileStat.st_mtime_ns, fileStat.st_size)


def _cardsFromData(data: list, path: str) -> list[Card]:
    """
    Build Card objects from the dicts read from a deck file.
    Repairs hand-edited values that are the wrong type, and raises ValueError
    when an entry is not a card at all.
    """

    try:
        return [Card.fromDict(each) for each in data]
    except (TypeError, AttributeError, KeyError, ValueError) as error:
        raise ValueError(f"The deck file '{path}' is damaged: {error}") from error


def _normaliseDeckData(data: list, path: str) -> list[dict]:
    """
    The card dicts read from a deck file, repaired to what this program would write.
    Used to compare with what this window last read, so a hand-edited but usable
    file does not look like a change made by another window on every save.
    """

    return [eachCard.toDict() for eachCard in _cardsFromData(data, path)]


def _readDeckData(path: str) -> list[dict]:
    """
    Read the list of card dicts from a deck file, without building Card objects.
    Returns an empty list if the file does not exist or is empty.
    Raises ValueError with a message the user can act on if the path cannot be used as a
    deck.
    """

    if not os.path.exists(path):
        return []

    # Checked before opening: Windows reports a folder as "permission denied".
    if os.path.isdir(path):
        raise ValueError(
            f"'{path}' is a folder, not a deck file. "
            "Point WORD_FLASHCARD_DECK at a .json file, "
            "for example ~/.word_flashcard/deck.json."
        )

    try:
        with open(path, encoding="utf-8") as deckFile:
            content = deckFile.read().strip()

    except PermissionError:
        raise ValueError(
            f"The deck file '{path}' cannot be read: permission denied."
        ) from None

    except UnicodeDecodeError:
        raise ValueError(
            f"The deck file '{path}' is damaged: it is not UTF-8 text."
        ) from None

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
        raise ValueError(
            f"The deck file '{path}' is damaged: "
            "the file does not contain a list of cards"
        )

    return data


def _writeDeckData(data: list[dict], path: str) -> None:
    """
    Write the card dicts to the deck file: temporary file first, then move it into
    place.
    """

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    tmpPath = path + ".tmp"

    try:
        # One write of the whole text is much faster than json.dump's many small writes.
        with open(tmpPath, "w", encoding="utf-8") as deckFile:
            deckFile.write(json.dumps(data, ensure_ascii=False, indent=2))

        os.replace(tmpPath, path)

    except OSError as error:
        try:
            os.remove(tmpPath)
        except OSError:
            pass

        reason = (error.strerror or str(error)).lower()
        raise DeckSaveError(
            f"The deck file '{path}' cannot be written: {reason}."
        ) from error


def _deckKey(path: str) -> str:
    """
    The key used to remember a deck file: the same file always gets the same key.
    """

    return os.path.abspath(os.path.expanduser(path))


def _wordKey(word: object) -> str:
    """
    The word a card is filed under, matching how findCard compares words.
    """

    return word.strip().casefold() if isinstance(word, str) else ""


def _cardKey(cardData: dict) -> str:
    return _wordKey(cardData.get("word"))


def backupPath(path: str) -> str:
    """
    Where the backup of a deck file is saved, e.g. "deck.json" -> "deck.backup.json".
    """

    root, extension = os.path.splitext(path)
    return root + ".backup" + (extension or ".json")


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
    Return the card for a word (ignoring upper / lower case), or None if it is not in
    the deck.
    """

    target = word.strip().casefold()

    for eachCard in cards:
        if eachCard.word.casefold() == target:
            return eachCard

    return None


def addCard(cards: list[Card], card: Card) -> bool:
    """
    Add a card to the deck. Returns False (and adds nothing) if the word is already in
    the deck.
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

    return [eachCard for eachCard in cards if leitnerScheduler.isDue(eachCard, today)]


def nextDueDate(cards: list[Card]) -> str | None:
    """
    Return the earliest review date in the deck, or None if the deck is empty.
    """

    return min((eachCard.nextReview for eachCard in cards), default=None)
