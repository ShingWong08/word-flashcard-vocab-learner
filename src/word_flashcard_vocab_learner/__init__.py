"""A lightweight CLI flashcard tool for vocabulary learning and review."""

__version__ = "0.1.5"

import os
from datetime import date

import requests
from dotenv import find_dotenv, load_dotenv

from word_flashcard_vocab_learner import (
    cardDeck,
    connectFreeDictionaryAPI,
    exportDeckToCSV,
    genAITutor,
    importVocabulary,
    leitnerScheduler,
    removeWords,
    reviewCards,
    showProgress,
    speechHelper,
    terminalDisplay,
)
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card
from word_flashcard_vocab_learner.terminalDisplay import plural
from word_flashcard_vocab_learner.userInput import ask, askYesNo, isQuit

# Load API keys from .env once, when the package is imported.
# Every module of the package is imported through here, so they all see the keys.
load_dotenv(find_dotenv(usecwd=True))


CLEAR_COMMANDS = ["c", "clear", "cls"]
MAX_DECK_WORD_WIDTH = terminalDisplay.MAX_WORD_COLUMN_WIDTH
DECK_PAGE_SIZE = 30
NARROW_DECK_WIDTH = 70

EMPTY_DECK_MESSAGE = "Your deck is empty. Look up some words and add them first."
NOT_SAVED_MESSAGE = (
    "  Your progress was not saved. Fix the deck file problem, then try again."
)


def main(deckPath: str | None = None) -> None:
    """
    Run the flashcard app: show the main menu and repeat until the user quits.
    Parameters:
        Optional:
            - deckPath (str | None): Where the deck is saved. Default is
              cardDeck.defaultDeckPath().
    """

    if deckPath is None:
        deckPath = cardDeck.defaultDeckPath()

    try:
        cards = cardDeck.loadDeck(deckPath)
    except ValueError as error:
        message = str(error)
        print(ChatColor.paint(message, ChatColor.RED))

        if "damaged" in message:
            print(
                ChatColor.paint(
                    "Fix or move the file, then start again. Nothing was changed.",
                    ChatColor.ORANGE,
                )
            )

        return

    printWelcome(cards)

    actions = {
        "1": lookUpWords,
        "2": startReview,
        "3": importVocabulary.importVocabulary,
        "4": showDeck,
        "5": lambda cards, deckPath: showProgress.showProgress(cards),
        "6": exportDeck,
        "7": removeWords.removeWords,
        "8": editCard,
        "9": practiseOneWord,
    }

    try:
        while True:
            choice = askMenuChoice(cards)

            if isQuit(choice):
                break

            if choice.lower() in CLEAR_COMMANDS:
                terminalDisplay.clearScreen()
                continue

            if choice in actions:
                print()
                actions[choice](cards, deckPath)

                mergeNote = cardDeck.takeMergeNote(deckPath)
                if mergeNote is not None:
                    print(ChatColor.paint("  " + mergeNote, ChatColor.DARK_GRAY))
            elif choice != "":
                print(ChatColor.paint("Please choose 1 - 9, c or q.", ChatColor.ORANGE))

    except KeyboardInterrupt:
        print()

    print()
    print(ChatColor.paint("Goodbye!", ChatColor.BOLD, ChatColor.CYAN))


def printWelcome(cards: list[Card]) -> None:
    """
    Print the welcome message when the app starts, with the size of the deck and how
    many cards are due today.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck that was just loaded.
    """

    print()
    print(
        ChatColor.paint(
            "Welcome to the Word Flashcard Vocab Learner!",
            ChatColor.BOLD,
            ChatColor.CYAN,
        )
    )
    print("This package helps you learn English vocabulary more easily!")
    print()

    dueCount = len(cardDeck.getDueCards(cards, date.today()))
    print(
        ChatColor.paint(
            f"Your deck has {plural(len(cards), 'word')}, "
            f"{dueCount} due for review today.",
            ChatColor.DARK_GRAY,
        )
    )


def askMenuChoice(cards: list[Card]) -> str | None:
    """
    Print the main menu and return the user's choice.
    The "Review cards" item shows how many cards are due today, when there are any.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck, used to count the due cards.
    Returns:
        str | None: What the user typed (see userInput.ask), e.g. "1" to "9", "c" or
        "q". None if the user pressed Ctrl+C or Ctrl+Z / Ctrl+D.
    """

    dueCount = len(cardDeck.getDueCards(cards, date.today()))
    reviewLabel = "Review cards"
    if dueCount > 0:
        reviewLabel += ChatColor.paint(f"  ({dueCount} due)", ChatColor.ORANGE)

    options = [
        ("1", "Look up and add words"),
        ("2", reviewLabel),
        ("3", "Import words from a file (PDF, Word, scan, text)"),
        ("4", "View my deck"),
        ("5", "Progress"),
        ("6", "Export deck to CSV"),
        ("7", "Remove words"),
        ("8", "Edit a card"),
        ("9", "Practise one word"),
        ("", ""),
        ("c", "Clear the screen"),
        ("q", "Quit"),
    ]

    terminalDisplay.printHeading("Main menu")

    for key, label in options:
        if key == "":
            print()
        else:
            print(ChatColor.paint(f"  {key}. ", ChatColor.BOLD) + label)

    print()
    return ask("Choose: ", ChatColor.BOLD, ChatColor.YELLOW)


# ---------- Shared by several screens ----------


def isDeckEmpty(cards: list[Card], message: str = EMPTY_DECK_MESSAGE) -> bool:
    """
    Tell whether the deck has no cards, and if so, tell the user. Screens that need
    cards call this first and go back to the menu when it returns True.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck.
        Optional:
            - message (str): What to tell the user, in orange.
              Default: EMPTY_DECK_MESSAGE ("Your deck is empty. Look up some words and
              add them first.").
    Returns:
        bool: True if the deck is empty (the message was printed), otherwise False.
    """

    if cards:
        return False

    print(ChatColor.paint(message, ChatColor.ORANGE))
    return True


def printSaveError(error: Exception, note: str) -> None:
    """
    Show why the deck file could not be saved, then what that means for the user.

    Parameters:
        Mandatory:
            - error (Exception): The save error, usually a cardDeck.DeckSaveError. Its
              message is printed in red.
            - note (str): What happened to the user's change, printed in orange, e.g.
              "The change is in this session, but the deck file was not updated."
    """

    print(ChatColor.paint(f"  {error}", ChatColor.RED))
    print(ChatColor.paint(note, ChatColor.ORANGE))


class ProgressSaver:
    """
    Save the deck after every answer. If the deck cannot be written, say so once and
    keep the session going, so the answers of this session are not lost.
    Afterwards, failed tells whether a save went wrong.
    """

    def __init__(self, cards: list[Card], deckPath: str, note: str) -> None:
        """
        Set up the saver. Nothing is saved until the saver is called.

        Parameters:
            Mandatory:
                - cards (list[Card]): The whole deck to save each time.
                - deckPath (str): The deck file.
                - note (str): What to tell the user, in orange, when a save fails,
                  e.g. "  Your answers are kept for this session, but the deck file
                  was not updated."
        """

        self.cards = cards
        self.deckPath = deckPath
        self.note = note
        self.failed = False

    def __call__(self) -> None:
        if self.failed:
            return

        try:
            cardDeck.saveDeck(self.cards, self.deckPath)
        except cardDeck.DeckSaveError as error:
            self.failed = True
            print()
            printSaveError(error, self.note)


# ---------- 1. Look up and add words ----------


def lookUpWords(cards: list[Card], deckPath: str) -> None:
    """
    The "Look up and add words" screen: look up words one after another. An empty line
    or 'q' goes back to the menu.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. Words the user adds are appended to it.
            - deckPath (str): The deck file, saved after every added word.
    """

    print(
        ChatColor.paint(
            "Type an English word to look it up. "
            "Press Enter on an empty line to go back.",
            ChatColor.DARK_GRAY,
        )
    )

    while True:
        print()
        word = ask("Word: ", ChatColor.BOLD, ChatColor.YELLOW)

        if isQuit(word) or word == "":
            return

        print()
        showDefinitions(word, cards, deckPath)


def showDefinitions(word: str, cards: list[Card], deckPath: str) -> None:
    """
    Look up the word and print its definitions.
    If it was found: show the Chinese translation (AI tutor), offer the pronunciation
    (speech), and offer to add it to the deck. When the dictionary cannot be reached,
    the problem is printed instead.

    Parameters:
        Mandatory:
            - word (str): The word the user typed.
            - cards (list[Card]): The deck.
            - deckPath (str): The deck file.
    """

    try:
        result = connectFreeDictionaryAPI.getWordDefinition(word)
    except requests.RequestException as error:
        print(
            ChatColor.paint(f"Could not reach the dictionary: {error}", ChatColor.RED)
        )
        return

    print(connectFreeDictionaryAPI.formatWordDefinition(result))

    if not result["definitions"]:
        return

    translation = lookUpTranslation(result)
    if translation != "":
        print()
        print(
            ChatColor.paint("  Chinese: ", ChatColor.DARK_GRAY)
            + ChatColor.paint(translation, ChatColor.GREEN)
        )

    print()

    if speechHelper.isSpeechAvailable():
        offerPronunciation(result["word"])

    offerToAdd(result, translation, cards, deckPath)


def lookUpTranslation(result: dict) -> str:
    """
    Get the Chinese translation from the AI tutor, for the first meaning of the word.

    Parameters:
        Mandatory:
            - result (dict): The dictionary result (see getWordDefinition).
    Returns:
        str: The translation. "" if the AI tutor is not set up (an LLM_* setting
        is missing, see genAITutor.TUTOR_SETTINGS), or if it fails (the problem is
        then printed in orange).
    """

    if not genAITutor.isAIAvailable():
        return ""

    definitions = result["definitions"]
    firstDefinition = definitions[0] if definitions else ""

    try:
        return genAITutor.translateWord(result["word"], firstDefinition)
    except Exception as error:
        print(
            ChatColor.paint(
                f"Could not get the Chinese translation: {error}", ChatColor.ORANGE
            )
        )
        return ""


def offerPronunciation(word: str) -> None:
    """
    Ask whether to play the word's pronunciation, and play it if the user says yes.
    Enter means no. A problem while playing is printed, not raised.

    Parameters:
        Mandatory:
            - word (str): The word to pronounce.
    """

    if not askYesNo("Play pronunciation? (y/N) ", default=False):
        return

    try:
        speechHelper.pronounce(word)
    except Exception as error:
        print(ChatColor.paint(f"Could not play pronunciation: {error}", ChatColor.RED))


def offerToAdd(
    result: dict, translation: str, cards: list[Card], deckPath: str
) -> None:
    """
    Ask whether to add the word to the deck, unless it is already there (then its box is
    shown instead). Enter means no. The deck is saved right after the word is added.

    Parameters:
        Mandatory:
            - result (dict): The dictionary result (see getWordDefinition).
            - translation (str): The Chinese translation, or "".
            - cards (list[Card]): The deck. A new card is appended to it.
            - deckPath (str): The deck file. If it cannot be written, the word stays in
              this session and the user is told.
    """

    word = result["word"]

    existingCard = cardDeck.findCard(cards, word)
    if existingCard is not None:
        print(
            ChatColor.paint(
                f'"{existingCard.word}" is already in your deck '
                f"(box {existingCard.box}).",
                ChatColor.DARK_GRAY,
            )
        )
        return

    if not askYesNo("Add to your deck? (y/N) ", default=False):
        return

    cardDeck.addCard(cards, Card.fromLookup(result, translation))

    try:
        cardDeck.saveDeck(cards, deckPath)
    except cardDeck.DeckSaveError as error:
        printSaveError(
            error, f'"{word}" is in this session, but the deck file was not updated.'
        )
        return

    print(
        ChatColor.paint(
            f'Added "{word}" to your deck ({plural(len(cards), "word")}).',
            ChatColor.GREEN,
        )
    )


# ---------- 2. Review cards ----------


def startReview(cards: list[Card], deckPath: str) -> None:
    """
    The "Review cards" screen: review the cards that are due today. If none are due,
    offer extra practice with all cards (extra practice does not change boxes or review
    dates). After each batch of 20 cards the user can carry on with the rest of the due
    cards.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. Reviewed cards are changed in place.
            - deckPath (str): The deck file, saved after every answer (see
              ProgressSaver).
    """

    if isDeckEmpty(cards):
        return

    today = date.today()
    cardsToReview = cardDeck.getDueCards(cards, today)
    updateSchedule = bool(cardsToReview)

    if updateSchedule:
        print(
            ChatColor.paint(
                f"Due today: {plural(len(cardsToReview), 'card')}.", ChatColor.CYAN
            )
        )
    else:
        print(
            ChatColor.paint(
                f"No cards are due today. Next review: {cardDeck.nextDueDate(cards)}.",
                ChatColor.GREEN,
            )
        )
        print()

        if not askYesNo(
            "Practise all cards anyway? Your progress will not change. (y/N) ",
            default=False,
        ):
            return

        cardsToReview = list(cards)

    print()
    mode = askReviewMode()
    if mode is None:
        return

    saveProgress = ProgressSaver(
        cards,
        deckPath,
        "  Your answers are kept for this session, but the deck file was not updated.",
    )

    while True:
        summary = reviewCards.reviewCards(
            cardsToReview,
            mode,
            saveProgress=saveProgress,
            today=today,
            updateSchedule=updateSchedule,
        )
        printSummary(summary)

        if saveProgress.failed:
            print(ChatColor.paint(NOT_SAVED_MESSAGE, ChatColor.ORANGE))
            return

        if not updateSchedule or summary["reviewed"] == 0:
            return

        remainingDue = cardDeck.getDueCards(cards, today)
        if not remainingDue:
            return

        nextBatch = min(len(remainingDue), reviewCards.MAX_CARDS_PER_SESSION)
        print()
        if not askYesNo(
            f"Continue with the next {plural(nextBatch, 'card')}? (y/N) ", default=False
        ):
            return

        cardsToReview = remainingDue
        print()


def askReviewMode() -> str | None:
    """
    Let the user choose a review mode. Returns None to go back to the menu.
    """

    modes = reviewCards.availableModes()
    nameWidth = max(map(len, reviewCards.MODE_NAMES.values()))

    print(ChatColor.paint("Review modes:", ChatColor.BOLD))
    print()

    for index, eachMode in enumerate(modes, start=1):
        name = ChatColor.paint(
            f"{reviewCards.MODE_NAMES[eachMode]:<{nameWidth}}", ChatColor.BOLD
        )
        description = ChatColor.paint(
            reviewCards.MODE_DESCRIPTIONS[eachMode], ChatColor.DARK_GRAY
        )
        print(f"  {index}. {name}   {description}")

    missingModes = []
    if not speechHelper.isSpeechAvailable():
        missingModes.append(
            "Listening, Speaking: set ELEVENLABS_API_KEY and run  "
            'pip install ".[speech]"'
        )
    missingAI = genAITutor.missingAISettings()
    if missingAI:
        missingModes.append(f"Sentence: set {', '.join(missingAI)} in .env")

    if missingModes:
        print()
        print(ChatColor.paint("  More modes:", ChatColor.DARK_GRAY))
        for eachNote in missingModes:
            print(
                terminalDisplay.wrapParagraph(
                    eachNote,
                    "    - ",
                    prefixStyles=(ChatColor.DARK_GRAY,),
                    textStyles=(ChatColor.DARK_GRAY,),
                )
            )

    print()

    while True:
        choice = ask("Choose a mode (Enter = 1, q = back): ", ChatColor.YELLOW)

        if isQuit(choice):
            return None

        if choice == "":
            return modes[0]

        if choice.isdigit() and 1 <= int(choice) <= len(modes):
            return modes[int(choice) - 1]

        print(
            ChatColor.paint(
                f"Please choose a number from 1 to {len(modes)}.", ChatColor.ORANGE
            )
        )


def printSummary(summary: dict) -> None:
    """
    Print the "Session finished" screen after a review: how many cards were reviewed,
    how many were right and wrong, and the score in percent.

    Parameters:
        Mandatory:
            - summary (dict): The result of reviewCards.reviewCards: {"reviewed": int,
              "correct": int, "wrong": int, "stopped": bool}. When no card was
              reviewed, only "No cards reviewed." is shown.
    """

    reviewed = summary["reviewed"]

    terminalDisplay.printHeading("Session finished")

    if reviewed == 0:
        print(ChatColor.paint("  No cards reviewed.", ChatColor.DARK_GRAY))
        return

    correct = summary["correct"]
    percent = round(correct * 100 / reviewed)

    print(terminalDisplay.labelLine("Reviewed", plural(reviewed, "card"), 8))
    print(
        terminalDisplay.labelLine(
            "Correct", ChatColor.paint(correct, ChatColor.GREEN), 8
        )
    )
    print(
        terminalDisplay.labelLine(
            "Wrong", ChatColor.paint(summary["wrong"], ChatColor.RED), 8
        )
    )
    print(terminalDisplay.labelLine("Score", f"{percent}%", 8))


# ---------- 4. View my deck ----------


def showDeck(cards: list[Card], deckPath: str) -> None:
    """
    The "View my deck" screen: list every card with its box, next review date, score
    and translation. Long decks are shown a page at a time (DECK_PAGE_SIZE words), so
    the numbers stay readable. A terminal narrower than NARROW_DECK_WIDTH shows each
    card on its own lines instead of a table, and long words and translations are
    shortened with "…" so nothing runs past the edge of the screen.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. Cards are listed in alphabetical order and
              numbered like on the "Remove words" screen.
            - deckPath (str): The deck file, shown at the end so the user knows where
              the deck is saved.
    """

    if isDeckEmpty(cards):
        return

    today = date.today()
    dueCount = len(cardDeck.getDueCards(cards, today))

    terminalDisplay.printHeading(
        f"Your deck: {plural(len(cards), 'word')}, {dueCount} due today"
    )

    sortedCards = cardDeck.sortByWord(cards)
    cardCount = len(sortedCards)
    longestWord = max(len(eachCard.word) for eachCard in sortedCards)
    wordWidth = min(max(longestWord, len("Word")), MAX_DECK_WORD_WIDTH)
    numberWidth = len(str(cardCount))

    # The numbers are the same as on the "Remove words" screen.
    header = (
        f"  {'#':>{numberWidth}}  {'Word':<{wordWidth}}  Box  "
        f"{'Next review':<11}  Score  Chinese"
    )
    terminalWidth = terminalDisplay.screenWidth()
    narrow = terminalWidth < NARROW_DECK_WIDTH

    # The translation gets whatever room is left: the last column of the table, or its
    # own line.
    translationWidth = max(
        4, terminalWidth - (6 if narrow else numberWidth + wordWidth + 31)
    )

    if cardCount > DECK_PAGE_SIZE:
        print(
            ChatColor.paint(
                f"  {DECK_PAGE_SIZE} words per page. "
                "Press Enter for the next page, q to go back.",
                ChatColor.DARK_GRAY,
            )
        )
        print()

    for pageStart in range(0, cardCount, DECK_PAGE_SIZE):
        if not narrow:
            print(ChatColor.paint(header, ChatColor.BOLD))
            print(ChatColor.paint("  " + "─" * (len(header) - 2), ChatColor.DARK_GRAY))

        pageCards = sortedCards[pageStart : pageStart + DECK_PAGE_SIZE]

        for index, eachCard in enumerate(pageCards, start=pageStart + 1):
            isDue = leitnerScheduler.isDue(eachCard, today)
            score = f"{eachCard.correctCount}/{eachCard.timesReviewed()}"
            word = terminalDisplay.truncateText(eachCard.word, wordWidth)
            number = ChatColor.paint(f"{index:>{numberWidth}}", ChatColor.DARK_GRAY)
            translation = terminalDisplay.truncateText(
                eachCard.translation, translationWidth
            )

            if narrow:
                # A narrow terminal cannot line up a table, so each card gets its own
                # lines instead.
                whenDue = "due now" if isDue else f"next {eachCard.nextReview}"
                print(
                    f"  {number}  {ChatColor.paint(word, ChatColor.BOLD)}"
                    + ChatColor.paint(
                        f"  ·  box {eachCard.box}  ·  {whenDue}  ·  {score}",
                        ChatColor.DARK_GRAY,
                    )
                )

                if translation != "":
                    print("      " + ChatColor.paint(translation, ChatColor.GREEN))
                continue

            if isDue:
                nextReview = ChatColor.paint(f"{'due now':<11}", ChatColor.ORANGE)
            else:
                nextReview = f"{eachCard.nextReview:<11}"

            print(
                f"  {number}  {word:<{wordWidth}}  {eachCard.box:>3}  "
                f"{nextReview}  {score:>5}  {translation}"
            )

        print()

        if pageStart + DECK_PAGE_SIZE < cardCount:
            answer = ask("Enter = next page, q = back: ", ChatColor.DARK_GRAY)
            if isQuit(answer):
                return

    print(ChatColor.paint(f"  Saved in: {deckPath}", ChatColor.DARK_GRAY))


# ---------- 6. Export deck to CSV ----------


def exportDeck(cards: list[Card], deckPath: str) -> None:
    """
    The "Export deck to CSV" screen: save the deck as a CSV file for Excel, Google
    Sheets, Quizlet or Anki. Enter uses DEFAULT_EXPORT_FILE ("vocabulary.csv"); a
    folder gets that file name inside it; a name without an extension gets ".csv"; and
    an existing file is only replaced when the user says yes.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck to export.
            - deckPath (str): The deck file. Not used here, but every menu screen takes
              the same two parameters.
    """

    if isDeckEmpty(cards, "Your deck is empty, so there is nothing to export."):
        return

    defaultFile = exportDeckToCSV.DEFAULT_EXPORT_FILE

    answer = ask(f"Save as (Enter = {defaultFile}, q = back): ", ChatColor.YELLOW)
    if isQuit(answer):
        return

    path = importVocabulary.cleanPath(answer) if answer != "" else defaultFile

    if os.path.isdir(path):
        path = os.path.join(path, defaultFile)

    if os.path.splitext(path)[1] == "":
        path += ".csv"

    if os.path.exists(path) and not askYesNo(
        f"{path} already exists. Replace it? (y/N) ", default=False
    ):
        return

    try:
        count = exportDeckToCSV.exportDeckToCSV(cards, path)
    except OSError as error:
        print(ChatColor.paint(f"Could not save the file: {error}", ChatColor.RED))
        return

    print(
        ChatColor.paint(
            f"Exported {plural(count, 'word')} to {os.path.abspath(path)}",
            ChatColor.GREEN,
        )
    )


# ---------- 8. Edit a card ----------


def editCard(cards: list[Card], deckPath: str) -> None:
    """
    The "Edit a card" screen: change a card that is already in the deck: its word, its
    Chinese translation or its meaning. Pressing Enter on a question keeps the current
    value; "-" clears that part. A new word that is already in the deck is refused, and
    a new meaning replaces all the definitions with that one line (and removes the
    example sentences, which belonged to the old definitions).

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. The card is changed in place.
            - deckPath (str): The deck file, saved once all questions are answered. If
              it cannot be written, the change stays in this session and the user is
              told.
    """

    if isDeckEmpty(cards):
        return

    word = ask("Word to edit (Enter = back): ", ChatColor.BOLD, ChatColor.YELLOW)
    if isQuit(word) or word == "":
        return

    card = cardDeck.findCard(cards, word)
    if card is None:
        print(ChatColor.paint(f'"{word}" is not in your deck.', ChatColor.ORANGE))
        return

    print()
    print(reviewCards.formatCardBack(card))
    print()

    newWord = ask("New word (Enter = keep): ", ChatColor.YELLOW)
    if isQuit(newWord):
        return

    if newWord != "" and newWord.casefold() != card.word.casefold():
        if cardDeck.findCard(cards, newWord) is not None:
            print(
                ChatColor.paint(
                    f'"{newWord}" is already in your deck, so nothing was changed.',
                    ChatColor.ORANGE,
                )
            )
            return

        card.word = newWord

    translation = ask("New Chinese (Enter = keep, - = clear): ", ChatColor.YELLOW)
    if isQuit(translation):
        return

    if translation == "-":
        card.translation = ""
    elif translation != "":
        card.translation = translation

    definition = ask(
        "New meaning, one line (Enter = keep, - = clear): ", ChatColor.YELLOW
    )
    if isQuit(definition):
        return

    if definition == "-":
        card.definitions = []
        card.examples = []
    elif definition != "":
        card.definitions = [definition]
        card.examples = [[]]

    try:
        cardDeck.saveDeck(cards, deckPath)
    except cardDeck.DeckSaveError as error:
        printSaveError(
            error, "The change is in this session, but the deck file was not updated."
        )
        return

    print(ChatColor.paint(f'Updated "{card.word}".', ChatColor.GREEN))


# ---------- 9. Practise one word ----------


def practiseOneWord(cards: list[Card], deckPath: str) -> None:
    """
    The "Practise one word" screen: review a single card, whatever its next review
    date, in the mode the user picks. The answer counts like a normal review: the box
    and next review date change.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. The card is changed in place.
            - deckPath (str): The deck file, saved after the answer (see
              ProgressSaver).
    """

    if isDeckEmpty(cards):
        return

    word = ask("Practise which word (Enter = back): ", ChatColor.BOLD, ChatColor.YELLOW)
    if isQuit(word) or word == "":
        return

    card = cardDeck.findCard(cards, word)
    if card is None:
        print(ChatColor.paint(f'"{word}" is not in your deck.', ChatColor.ORANGE))
        return

    print()
    mode = askReviewMode()
    if mode is None:
        return

    saveProgress = ProgressSaver(
        cards,
        deckPath,
        "  Your answer is kept for this session, but the deck file was not updated.",
    )

    summary = reviewCards.reviewCards(
        [card], mode, saveProgress=saveProgress, today=date.today(), updateSchedule=True
    )
    printSummary(summary)

    if saveProgress.failed:
        print(ChatColor.paint(NOT_SAVED_MESSAGE, ChatColor.ORANGE))


if __name__ == "__main__":
    main()
