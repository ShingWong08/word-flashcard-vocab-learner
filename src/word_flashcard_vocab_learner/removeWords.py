import fnmatch
import re

from word_flashcard_vocab_learner import cardDeck, leitnerScheduler, terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card
from word_flashcard_vocab_learner.terminalDisplay import plural
from word_flashcard_vocab_learner.userInput import ask, askYesNo, isQuit


ALL_COMMANDS = ["all", "everything"]
UNDO_COMMANDS = ["u", "undo"]
LIST_COMMANDS = ["l", "list"]
HELP_COMMANDS = ["h", "help", "?"]
MASTERED_COMMANDS = ["mastered"]
REMOVE_ALL_CONFIRMATION = "delete all"

HELP_LINES = [
    ("banana, accept", "words (separate them with commas)"),
    ("1,3,5-8", "numbers from the list"),
    ("amb*", 'words that start with "amb" (* = any letters)'),
    ("box 1", "every card in box 1 (box 5 = mastered words)"),
    ("all", "every word in your deck"),
    ("u", "undo the last removal"),
    ("l", "show the list again"),
]


# ---------- Choosing cards ----------

def selectByNumbers(part: str, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:

    """
    Turn numbers and ranges such as "1 3 5-8" into cards.
    Returns (cards, problems).
    """

    selected = []
    problems = []
    count = len(numberedCards)

    part = re.sub(r"\s*-\s*", "-", part.strip())   # "5 - 8" -> "5-8"

    for eachItem in part.split():
        rangeMatch = re.fullmatch(r"(\d+)-(\d+)", eachItem)

        if rangeMatch is not None:
            start, end = int(rangeMatch.group(1)), int(rangeMatch.group(2))
            if start > end:
                start, end = end, start
        elif eachItem.isdigit():
            start = end = int(eachItem)
        else:
            problems.append(f'"{eachItem}" is not a number or a range like 5-8.')
            continue

        if start < 1 or end > count:
            problems.append(f"There is no number {eachItem}. Choose from 1 to {count}.")
            continue

        for eachNumber in range(start, end + 1):
            selected.append(numberedCards[eachNumber - 1])

    return selected, problems


def selectByPattern(pattern: str, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:

    """
    Select the words that match a pattern with * (any letters) or ? (one letter), e.g. "amb*".
    """

    selected = []
    for eachCard in numberedCards:
        if fnmatch.fnmatchcase(eachCard.word.casefold(), pattern.casefold()):
            selected.append(eachCard)

    if len(selected) == 0:
        return [], [f'No words match "{pattern}".']

    return selected, []


def selectByWord(word: str, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:

    """
    Select a word or phrase. If "cat dog" is not a phrase in the deck but "cat" and "dog" both are,
    both are selected (so commas are not strictly needed).
    """

    card = cardDeck.findCard(numberedCards, word)
    if card is not None:
        return [card], []

    separateWords = word.split()
    if len(separateWords) > 1:
        cards = []
        for eachWord in separateWords:
            eachCard = cardDeck.findCard(numberedCards, eachWord)
            if eachCard is None:
                break
            cards.append(eachCard)
        else:
            return cards, []

    return [], [f'"{word}" is not in your deck.']


def selectByBox(box: int, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:

    if box < leitnerScheduler.MIN_BOX or box > leitnerScheduler.MAX_BOX:
        return [], [f"There is no box {box}. Boxes go from {leitnerScheduler.MIN_BOX} to {leitnerScheduler.MAX_BOX}."]

    selected = []
    for eachCard in numberedCards:
        if leitnerScheduler.clampBox(eachCard.box) == box:
            selected.append(eachCard)

    if len(selected) == 0:
        return [], [f"There are no cards in box {box}."]

    return selected, []


def selectCards(answer: str, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:

    """
    Work out which cards the user wants to remove.

    Parameters:
        Mandatory:
            - answer (str): What the user typed, e.g. "banana, 3, 5-8", "amb*", "box 5" or "all".
            - numberedCards (list[Card]): The cards in the order they are numbered on screen.
    Returns:
        (cards, problems): the cards to remove, in list order without duplicates,
        and a message for every part that could not be understood.
    """

    lowered = answer.strip().lower()

    if lowered in ALL_COMMANDS:
        return list(numberedCards), []

    if lowered in MASTERED_COMMANDS:
        return selectByBox(leitnerScheduler.MAX_BOX, numberedCards)

    boxMatch = re.fullmatch(r"box\s*(\d+)", lowered)
    if boxMatch is not None:
        return selectByBox(int(boxMatch.group(1)), numberedCards)

    selected = []
    problems = []

    for eachPart in answer.split(","):
        part = eachPart.strip()

        if part == "":
            continue

        if re.fullmatch(r"[\d\s-]+", part):
            cards, partProblems = selectByNumbers(part, numberedCards)
        elif "*" in part or "?" in part:
            cards, partProblems = selectByPattern(part, numberedCards)
        else:
            cards, partProblems = selectByWord(part, numberedCards)

        selected.extend(cards)
        problems.extend(partProblems)

    return removeDuplicates(selected, numberedCards), problems


def removeDuplicates(selected: list[Card], numberedCards: list[Card]) -> list[Card]:

    """
    Keep each card once, in the same order as the numbered list.
    """

    selectedIds = set(id(eachCard) for eachCard in selected)
    return [eachCard for eachCard in numberedCards if id(eachCard) in selectedIds]


# ---------- Removing and undoing ----------

def removeCards(cards: list[Card], selected: list[Card], deckPath: str) -> None:

    """
    Remove the selected cards and save the deck. A backup of the old deck is saved first.
    """

    cardDeck.backupDeck(deckPath)

    selectedIds = set(id(eachCard) for eachCard in selected)
    cards[:] = [eachCard for eachCard in cards if id(eachCard) not in selectedIds]

    cardDeck.saveDeck(cards, deckPath)


def undoRemoval(cards: list[Card], removedCards: list[Card], deckPath: str) -> list[Card]:

    """
    Put removed cards back (with their boxes, dates and scores). Words that were added again
    in the meantime are skipped. Returns the cards that were put back.
    """

    restored = []

    for eachCard in removedCards:
        if cardDeck.addCard(cards, eachCard):
            restored.append(eachCard)

    cardDeck.saveDeck(cards, deckPath)

    return restored


# ---------- Screen ----------

def formatWordList(words: list[str], indent: str = "    ") -> str:
    return terminalDisplay.wrapParagraph(", ".join(words), indent, textStyles=(ChatColor.VIOLET,))


def printNumberedList(numberedCards: list[Card]) -> None:

    """
    Print the words in numbered columns, then how many cards are in each box.
    """

    numberWidth = len(str(len(numberedCards)))
    items = []
    for index, eachCard in enumerate(numberedCards, start=1):
        word = terminalDisplay.truncateText(eachCard.word, terminalDisplay.MAX_WORD_COLUMN_WIDTH)
        items.append(f"{index:>{numberWidth}}. {word}")

    print(terminalDisplay.formatColumns(items))
    print()

    boxCounts = {}
    for eachCard in numberedCards:
        box = leitnerScheduler.clampBox(eachCard.box)
        boxCounts[box] = boxCounts.get(box, 0) + 1

    boxTexts = []
    for eachBox in sorted(boxCounts):
        boxTexts.append(f"box {eachBox}: {boxCounts[eachBox]}")

    print(ChatColor.paint(f"  {plural(len(numberedCards), 'word')}  ·  " + ",  ".join(boxTexts), ChatColor.DARK_GRAY))


def printHelp() -> None:

    commandWidth = max(len(eachCommand) for eachCommand, _ in HELP_LINES)

    print(ChatColor.paint("  What to remove:", ChatColor.BOLD))
    for eachCommand, eachMeaning in HELP_LINES:
        print(f"    {ChatColor.paint(f'{eachCommand:<{commandWidth}}', ChatColor.YELLOW)}   {ChatColor.paint(eachMeaning, ChatColor.DARK_GRAY)}")

    print(ChatColor.paint("  Press Enter to go back.", ChatColor.DARK_GRAY))


def confirmRemoval(selected: list[Card], isEverything: bool) -> bool:

    """
    Show the words that will be removed and ask the user to confirm.
    Removing every word needs the user to type "delete all", so it cannot happen by accident.
    """

    print()
    if len(selected) == 1:
        print("  This word will be removed:")
    else:
        print(f"  These {len(selected)} words will be removed:")
    print(formatWordList([eachCard.word for eachCard in selected]))
    print()

    if isEverything:
        answer = ask(f'Type "{REMOVE_ALL_CONFIRMATION}" to remove every word in your deck: ', ChatColor.YELLOW)
        return answer is not None and answer.lower() == REMOVE_ALL_CONFIRMATION

    if len(selected) == 1:
        return bool(askYesNo("Remove it? (y/N) ", default=False))

    return bool(askYesNo("Remove them? (y/N) ", default=False))


def printUpdatedList(cards: list[Card]) -> None:

    """
    After a removal or undo the numbers change, so show the new list straight away.
    """

    print()

    if len(cards) == 0:
        return

    print(ChatColor.paint("  The numbers have changed:", ChatColor.DARK_GRAY))
    print()
    printNumberedList(cardDeck.sortByWord(cards))


def removeWords(cards: list[Card], deckPath: str) -> None:

    """
    The "Remove words" screen: remove words by name, number, pattern or box, or remove all,
    with undo for every removal made on this screen.
    """

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty, so there is nothing to remove.", ChatColor.ORANGE))
        return

    undoStack = []

    terminalDisplay.printHeading("Remove words")
    printNumberedList(cardDeck.sortByWord(cards))
    print()
    printHelp()

    while True:
        print()
        answer = ask("Remove: ", ChatColor.BOLD, ChatColor.YELLOW)

        if isQuit(answer) or answer == "":
            return

        lowered = answer.lower()
        numberedCards = cardDeck.sortByWord(cards)

        if lowered in HELP_COMMANDS:
            printHelp()
            continue

        if lowered in LIST_COMMANDS:
            print()
            if len(numberedCards) == 0:
                print(ChatColor.paint("  Your deck is empty.", ChatColor.DARK_GRAY))
            else:
                printNumberedList(numberedCards)
            continue

        if lowered in UNDO_COMMANDS:
            if len(undoStack) == 0:
                print(ChatColor.paint("Nothing to undo.", ChatColor.ORANGE))
                continue

            try:
                restored = undoRemoval(cards, undoStack.pop(), deckPath)
            except cardDeck.DeckSaveError as error:
                print(ChatColor.paint(f"  {error}", ChatColor.RED))
                print(ChatColor.paint("The words are back on this screen, but the deck file was not updated.", ChatColor.ORANGE))
                printUpdatedList(cards)
                continue

            print(ChatColor.paint(f"Put back {plural(len(restored), 'word')}:", ChatColor.GREEN))
            print(formatWordList([eachCard.word for eachCard in restored]))
            printUpdatedList(cards)
            continue

        if len(numberedCards) == 0:
            print(ChatColor.paint("Your deck is empty. Type u to undo, or press Enter to go back.", ChatColor.ORANGE))
            continue

        selected, problems = selectCards(answer, numberedCards)

        if len(problems) > 0:
            for eachProblem in problems:
                print(ChatColor.paint(f"  {eachProblem}", ChatColor.ORANGE))
            print(ChatColor.paint("Nothing was removed. Please check and try again (h = help).", ChatColor.ORANGE))
            continue

        if len(selected) == 0:
            continue

        # Typing "delete all" is only needed when several words would be removed at once
        # and nothing would be left; removing the last single word just needs y.
        isEverything = len(selected) == len(cards) and len(cards) > 1

        if not confirmRemoval(selected, isEverything):
            print(ChatColor.paint("Nothing was removed.", ChatColor.DARK_GRAY))
            continue

        try:
            removeCards(cards, selected, deckPath)
        except cardDeck.DeckSaveError as error:
            print(ChatColor.paint(f"  {error}", ChatColor.RED))
            print(ChatColor.paint("The words are removed on this screen, but the deck file was not updated.", ChatColor.ORANGE))

        undoStack.append(selected)

        print(ChatColor.paint(f"Removed {plural(len(selected), 'word')}.", ChatColor.GREEN) + ChatColor.paint("  Type u to undo.", ChatColor.DARK_GRAY))

        if len(cards) == 0:
            print(ChatColor.paint(f"  Your deck is now empty. A copy of the old deck was saved to {cardDeck.backupPath(deckPath)}", ChatColor.DARK_GRAY))

        printUpdatedList(cards)
