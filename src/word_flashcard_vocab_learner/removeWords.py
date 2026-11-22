import fnmatch
import re
from collections import Counter

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

DASH_WITH_SPACES = re.compile(r"\s*-\s*")
NUMBER_RANGE = re.compile(r"(\d+)-(\d+)")
NUMBERS_ONLY = re.compile(r"[\d\s-]+")
BOX_COMMAND = re.compile(r"box\s*(\d+)")


# ---------- Choosing cards ----------


def selectByNumbers(
    part: str, numberedCards: list[Card]
) -> tuple[list[Card], list[str]]:
    """
    Turn numbers and ranges such as "1 3 5-8" into cards.
    A range may be written backwards ("8-5") or with spaces ("5 - 8").

    Parameters:
        Mandatory:
            - part (str): One comma-separated part of the answer, holding only numbers,
              spaces and dashes.
            - numberedCards (list[Card]): The cards in the order they are numbered on
              screen (number 1 is the first card).
    Returns:
        tuple[list[Card], list[str]]: (cards, problems).
            - cards: The cards for the numbers, in the order typed (may repeat).
            - problems: A message for every item that is not a number or a range, or
              that is outside 1 to the number of cards.
    """

    selected = []
    problems = []
    count = len(numberedCards)

    for eachItem in DASH_WITH_SPACES.sub("-", part.strip()).split():  # "5 - 8" -> "5-8"
        rangeMatch = NUMBER_RANGE.fullmatch(eachItem)

        if rangeMatch is not None:
            start, end = sorted((int(rangeMatch.group(1)), int(rangeMatch.group(2))))
        elif eachItem.isdigit():
            start = end = int(eachItem)
        else:
            problems.append(f'"{eachItem}" is not a number or a range like 5-8.')
            continue

        if start < 1 or end > count:
            problems.append(f"There is no number {eachItem}. Choose from 1 to {count}.")
            continue

        selected.extend(numberedCards[start - 1 : end])

    return selected, problems


def selectByPattern(
    pattern: str, numberedCards: list[Card]
) -> tuple[list[Card], list[str]]:
    """
    Select the words that match a pattern with * (any letters) or ? (one letter), e.g.
    "amb*" or "?at".

    Parameters:
        Mandatory:
            - pattern (str): The pattern, compared with the whole word and ignoring
              upper / lower case.
            - numberedCards (list[Card]): The cards in the order they are numbered on
              screen.
    Returns:
        tuple[list[Card], list[str]]: (cards, problems): the matching cards in list
        order and no problems, or no cards and the message 'No words match "...".'
    """

    target = pattern.casefold()
    selected = [
        eachCard
        for eachCard in numberedCards
        if fnmatch.fnmatchcase(eachCard.word.casefold(), target)
    ]

    if not selected:
        return [], [f'No words match "{pattern}".']

    return selected, []


def selectByWord(word: str, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:
    """
    Select a word or phrase. If "cat dog" is not a phrase in the deck but "cat" and
    "dog" both are, both are selected (so commas are not strictly needed).

    Parameters:
        Mandatory:
            - word (str): The word or phrase, compared ignoring upper / lower case.
            - numberedCards (list[Card]): The cards in the order they are numbered on
              screen.
    Returns:
        tuple[list[Card], list[str]]: (cards, problems): the card(s) and no problems,
        or no cards and the message '"..." is not in your deck.' when the phrase is not
        in the deck and its words are not all in the deck either.
    """

    card = cardDeck.findCard(numberedCards, word)
    if card is not None:
        return [card], []

    separateWords = word.split()
    if len(separateWords) > 1:
        cards = [
            cardDeck.findCard(numberedCards, eachWord) for eachWord in separateWords
        ]
        if None not in cards:
            return cards, []

    return [], [f'"{word}" is not in your deck.']


def selectByBox(box: int, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:
    """
    Select every card in one Leitner box, e.g. for "box 1" or "mastered" (box 5).

    Parameters:
        Mandatory:
            - box (int): The box number. A box outside 1-5 is a problem, not an error.
            - numberedCards (list[Card]): The cards in the order they are numbered on
              screen.
    Returns:
        tuple[list[Card], list[str]]: (cards, problems): the cards in that box in list
        order and no problems, or no cards and a message saying that the box does not
        exist or is empty.
    """

    minBox = leitnerScheduler.MIN_BOX
    maxBox = leitnerScheduler.MAX_BOX

    if box < minBox or box > maxBox:
        return [], [f"There is no box {box}. Boxes go from {minBox} to {maxBox}."]

    selected = [
        eachCard
        for eachCard in numberedCards
        if leitnerScheduler.clampBox(eachCard.box) == box
    ]

    if not selected:
        return [], [f"There are no cards in box {box}."]

    return selected, []


def selectCards(answer: str, numberedCards: list[Card]) -> tuple[list[Card], list[str]]:
    """
    Work out which cards the user wants to remove.

    Parameters:
        Mandatory:
            - answer (str): What the user typed, e.g. "banana, 3, 5-8", "amb*", "box 5"
              or "all".
            - numberedCards (list[Card]): The cards in the order they are numbered on
              screen.
    Returns:
        (cards, problems): the cards to remove, in list order without duplicates,
        and a message for every part that could not be understood.
    """

    lowered = answer.strip().lower()

    if lowered in ALL_COMMANDS:
        return list(numberedCards), []

    if lowered in MASTERED_COMMANDS:
        return selectByBox(leitnerScheduler.MAX_BOX, numberedCards)

    boxMatch = BOX_COMMAND.fullmatch(lowered)
    if boxMatch is not None:
        return selectByBox(int(boxMatch.group(1)), numberedCards)

    selected = []
    problems = []

    for eachPart in answer.split(","):
        part = eachPart.strip()

        if part == "":
            continue

        if NUMBERS_ONLY.fullmatch(part):
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
    Cards are compared as objects, so two cards with the same word stay separate.

    Parameters:
        Mandatory:
            - selected (list[Card]): The chosen cards, in any order and possibly with
              repeats (e.g. from "cat, 1" when card 1 is "cat").
            - numberedCards (list[Card]): The cards in the order they are numbered on
              screen.
    Returns:
        list[Card]: Each chosen card once, in numbered-list order.
    """

    selectedIds = {id(eachCard) for eachCard in selected}
    return [eachCard for eachCard in numberedCards if id(eachCard) in selectedIds]


# ---------- Removing and undoing ----------


def removeCards(cards: list[Card], selected: list[Card], deckPath: str) -> None:
    """
    Remove the selected cards and save the deck. A backup of the old deck is saved
    first (see cardDeck.backupDeck).

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. It is changed in place.
            - selected (list[Card]): The card objects to remove.
            - deckPath (str): The deck file.
    Raises:
        cardDeck.DeckSaveError: When the deck file cannot be written. The cards are
        already removed from the list in memory by then.
    """

    cardDeck.backupDeck(deckPath)

    selectedIds = {id(eachCard) for eachCard in selected}
    cards[:] = [eachCard for eachCard in cards if id(eachCard) not in selectedIds]

    cardDeck.saveDeck(cards, deckPath)


def undoRemoval(
    cards: list[Card], removedCards: list[Card], deckPath: str
) -> list[Card]:
    """
    Put removed cards back (with their boxes, dates and scores). Words that were added
    again in the meantime are skipped. The deck is saved afterwards.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. It is changed in place.
            - removedCards (list[Card]): The cards of one earlier removal.
            - deckPath (str): The deck file.
    Returns:
        list[Card]: The cards that were put back.
    Raises:
        cardDeck.DeckSaveError: When the deck file cannot be written. The cards are
        already back in the list in memory by then.
    """

    restored = []

    for eachCard in removedCards:
        if cardDeck.addCard(cards, eachCard):
            restored.append(eachCard)

    cardDeck.saveDeck(cards, deckPath)

    return restored


# ---------- Screen ----------


def formatWordList(words: list[str], indent: str = "    ") -> str:
    """
    Show words as one comma-separated list in violet, wrapped to the screen width.

    Parameters:
        Mandatory:
            - words (list[str]): The words, e.g. the ones about to be removed.
        Optional:
            - indent (str): Text before every line. Default: "    " (four spaces).
    Returns:
        str: The wrapped list.
    """

    return terminalDisplay.wrapParagraph(
        ", ".join(words), indent, textStyles=(ChatColor.VIOLET,)
    )


def printNumberedList(numberedCards: list[Card]) -> None:
    """
    Print the words in numbered columns, then how many cards are in each box.
    The numbers are the ones the user types to remove words, and the same as on the
    "View my deck" screen.

    Parameters:
        Mandatory:
            - numberedCards (list[Card]): The cards, already in numbered (alphabetical)
              order. Long words are shortened with "…" so the columns line up.
    """

    numberWidth = len(str(len(numberedCards)))
    words = [
        terminalDisplay.truncateText(
            eachCard.word, terminalDisplay.MAX_WORD_COLUMN_WIDTH
        )
        for eachCard in numberedCards
    ]
    items = [
        f"{index:>{numberWidth}}. {eachWord}"
        for index, eachWord in enumerate(words, start=1)
    ]

    print(terminalDisplay.formatColumns(items))
    print()

    boxCounts = Counter(
        leitnerScheduler.clampBox(eachCard.box) for eachCard in numberedCards
    )
    boxTexts = ",  ".join(
        f"box {eachBox}: {boxCounts[eachBox]}" for eachBox in sorted(boxCounts)
    )

    print(
        ChatColor.paint(
            f"  {plural(len(numberedCards), 'word')}  ·  {boxTexts}",
            ChatColor.DARK_GRAY,
        )
    )


def printHelp() -> None:
    commandWidth = max(len(eachCommand) for eachCommand, _ in HELP_LINES)

    print(ChatColor.paint("  What to remove:", ChatColor.BOLD))
    for eachCommand, eachMeaning in HELP_LINES:
        command = ChatColor.paint(f"{eachCommand:<{commandWidth}}", ChatColor.YELLOW)
        print(f"    {command}   {ChatColor.paint(eachMeaning, ChatColor.DARK_GRAY)}")

    print(ChatColor.paint("  Press Enter to go back.", ChatColor.DARK_GRAY))


def confirmRemoval(selected: list[Card], isEverything: bool) -> bool:
    """
    Show the words that will be removed and ask the user to confirm.
    Removing every word needs the user to type "delete all", so it cannot happen by
    accident.

    Parameters:
        Mandatory:
            - selected (list[Card]): The cards about to be removed.
            - isEverything (bool): True when the removal would empty a deck of more
              than one word; then "delete all" has to be typed instead of y.
    Returns:
        bool: True if the user confirmed. False for no, Enter, a wrong confirmation
        text, or stopping (q, Ctrl+C or Ctrl+Z / Ctrl+D).
    """

    isOne = len(selected) == 1

    print()
    print(
        "  This word will be removed:"
        if isOne
        else f"  These {len(selected)} words will be removed:"
    )
    print(formatWordList([eachCard.word for eachCard in selected]))
    print()

    if isEverything:
        answer = ask(
            f'Type "{REMOVE_ALL_CONFIRMATION}" to remove every word in your deck: ',
            ChatColor.YELLOW,
        )
        return answer is not None and answer.lower() == REMOVE_ALL_CONFIRMATION

    return bool(
        askYesNo("Remove it? (y/N) " if isOne else "Remove them? (y/N) ", default=False)
    )


def printUpdatedList(cards: list[Card]) -> None:
    """
    After a removal or undo the numbers change, so show the new list straight away.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck after the change. Nothing is listed when it
              is empty.
    """

    print()

    if not cards:
        return

    print(ChatColor.paint("  The numbers have changed:", ChatColor.DARK_GRAY))
    print()
    printNumberedList(cardDeck.sortByWord(cards))


def removeWords(cards: list[Card], deckPath: str) -> None:
    """
    The "Remove words" screen: remove words by name, number, pattern or box, or remove
    all, with undo for every removal made on this screen. The user can also show the
    list again (l) or the help (h); Enter or q goes back to the main menu.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. It is changed in place.
            - deckPath (str): The deck file, saved after every removal and undo. A
              backup is made before every removal.
    """

    if not cards:
        print(
            ChatColor.paint(
                "Your deck is empty, so there is nothing to remove.", ChatColor.ORANGE
            )
        )
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
            if numberedCards:
                printNumberedList(numberedCards)
            else:
                print(ChatColor.paint("  Your deck is empty.", ChatColor.DARK_GRAY))
            continue

        if lowered in UNDO_COMMANDS:
            if not undoStack:
                print(ChatColor.paint("Nothing to undo.", ChatColor.ORANGE))
                continue

            try:
                restored = undoRemoval(cards, undoStack.pop(), deckPath)
            except cardDeck.DeckSaveError as error:
                print(ChatColor.paint(f"  {error}", ChatColor.RED))
                print(
                    ChatColor.paint(
                        "The words are back on this screen, "
                        "but the deck file was not updated.",
                        ChatColor.ORANGE,
                    )
                )
                printUpdatedList(cards)
                continue

            print(
                ChatColor.paint(
                    f"Put back {plural(len(restored), 'word')}:", ChatColor.GREEN
                )
            )
            print(formatWordList([eachCard.word for eachCard in restored]))
            printUpdatedList(cards)
            continue

        if not numberedCards:
            print(
                ChatColor.paint(
                    "Your deck is empty. Type u to undo, or press Enter to go back.",
                    ChatColor.ORANGE,
                )
            )
            continue

        selected, problems = selectCards(answer, numberedCards)

        if problems:
            for eachProblem in problems:
                print(ChatColor.paint(f"  {eachProblem}", ChatColor.ORANGE))
            print(
                ChatColor.paint(
                    "Nothing was removed. Please check and try again (h = help).",
                    ChatColor.ORANGE,
                )
            )
            continue

        if not selected:
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
            print(
                ChatColor.paint(
                    "The words are removed on this screen, "
                    "but the deck file was not updated.",
                    ChatColor.ORANGE,
                )
            )

        undoStack.append(selected)

        print(
            ChatColor.paint(
                f"Removed {plural(len(selected), 'word')}.", ChatColor.GREEN
            )
            + ChatColor.paint("  Type u to undo.", ChatColor.DARK_GRAY)
        )

        if not cards:
            print(
                ChatColor.paint(
                    "  Your deck is now empty. A copy of the old deck was saved to "
                    + cardDeck.backupPath(deckPath),
                    ChatColor.DARK_GRAY,
                )
            )

        printUpdatedList(cards)
