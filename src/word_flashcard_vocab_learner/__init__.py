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
load_dotenv(find_dotenv(usecwd=True))


CLEAR_COMMANDS = ["c", "clear", "cls"]
MAX_DECK_WORD_WIDTH = terminalDisplay.MAX_WORD_COLUMN_WIDTH
DECK_PAGE_SIZE = 30
NARROW_DECK_WIDTH = 70


def main(deckPath: str | None = None) -> None:

    """
    Run the flashcard app: show the main menu and repeat until the user quits.
    Parameters:
        Optional:
            - deckPath (str | None): Where the deck is saved. Default is cardDeck.defaultDeckPath().
    """

    if deckPath is None:
        deckPath = cardDeck.defaultDeckPath()

    try:
        cards = cardDeck.loadDeck(deckPath)
    except ValueError as error:
        message = str(error)
        print(ChatColor.paint(message, ChatColor.RED))

        if "damaged" in message:
            print(ChatColor.paint("Fix or move the file, then start again. Nothing was changed.", ChatColor.ORANGE))

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
    print()
    print(ChatColor.paint("Welcome to the Word Flashcard Vocab Learner!", ChatColor.BOLD, ChatColor.CYAN))
    print("This package helps you learn English vocabulary more easily!")
    print()

    dueCount = len(cardDeck.getDueCards(cards, date.today()))
    print(ChatColor.paint(f"Your deck has {plural(len(cards), 'word')}, {dueCount} due for review today.", ChatColor.DARK_GRAY))


def askMenuChoice(cards: list[Card]) -> str | None:

    """
    Print the main menu and return the user's choice.
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


# ---------- 1. Look up and add words ----------

def lookUpWords(cards: list[Card], deckPath: str) -> None:

    """
    Look up words one after another. An empty line or 'q' goes back to the menu.
    """

    print(ChatColor.paint("Type an English word to look it up. Press Enter on an empty line to go back.", ChatColor.DARK_GRAY))

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
    If it was found: show the Chinese translation (AI tutor), offer the pronunciation (speech),
    and offer to add it to the deck.
    """

    try:
        result = connectFreeDictionaryAPI.getWordDefinition(word)
    except requests.RequestException as error:
        print(ChatColor.paint(f"Could not reach the dictionary: {error}", ChatColor.RED))
        return

    print(connectFreeDictionaryAPI.formatWordDefinition(result))

    if len(result["definitions"]) == 0:
        return

    translation = lookUpTranslation(result)
    if translation != "":
        print()
        print(ChatColor.paint("  Chinese: ", ChatColor.DARK_GRAY) + ChatColor.paint(translation, ChatColor.GREEN))

    print()

    if speechHelper.isSpeechAvailable():
        offerPronunciation(result["word"])

    offerToAdd(result, translation, cards, deckPath)


def lookUpTranslation(result: dict) -> str:

    """
    Get the Chinese translation from the AI tutor. Returns "" if the AI tutor is not set up or fails.
    """

    if not genAITutor.isAIAvailable():
        return ""

    firstDefinition = ""
    if len(result["definitions"]) > 0:
        firstDefinition = result["definitions"][0]

    try:
        return genAITutor.translateWord(result["word"], firstDefinition)
    except Exception as error:
        print(ChatColor.paint(f"Could not get the Chinese translation: {error}", ChatColor.ORANGE))
        return ""


def offerPronunciation(word: str) -> None:

    """
    Ask whether to play the word's pronunciation, and play it if the user says yes.
    """

    if not askYesNo("Play pronunciation? (y/N) ", default=False):
        return

    try:
        speechHelper.pronounce(word)
    except Exception as error:
        print(ChatColor.paint(f"Could not play pronunciation: {error}", ChatColor.RED))


def offerToAdd(result: dict, translation: str, cards: list[Card], deckPath: str) -> None:

    """
    Ask whether to add the word to the deck, unless it is already there.
    """

    existingCard = cardDeck.findCard(cards, result["word"])
    if existingCard is not None:
        print(ChatColor.paint(f'"{existingCard.word}" is already in your deck (box {existingCard.box}).', ChatColor.DARK_GRAY))
        return

    if not askYesNo("Add to your deck? (y/N) ", default=False):
        return

    cardDeck.addCard(cards, Card.fromLookup(result, translation))

    try:
        cardDeck.saveDeck(cards, deckPath)
    except cardDeck.DeckSaveError as error:
        print(ChatColor.paint(f'  {error}', ChatColor.RED))
        print(ChatColor.paint(f'"{result["word"]}" is in this session, but the deck file was not updated.', ChatColor.ORANGE))
        return

    print(ChatColor.paint(f'Added "{result["word"]}" to your deck ({plural(len(cards), "word")}).', ChatColor.GREEN))


# ---------- 2. Review cards ----------

def startReview(cards: list[Card], deckPath: str) -> None:

    """
    Review the cards that are due today. If none are due, offer extra practice
    with all cards (extra practice does not change boxes or review dates).
    After each batch of 20 cards the user can carry on with the rest of the due cards.
    """

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty. Look up some words and add them first.", ChatColor.ORANGE))
        return

    today = date.today()
    cardsToReview = cardDeck.getDueCards(cards, today)
    updateSchedule = True

    if len(cardsToReview) == 0:
        print(ChatColor.paint(f"No cards are due today. Next review: {cardDeck.nextDueDate(cards)}.", ChatColor.GREEN))
        print()

        if not askYesNo("Practise all cards anyway? Your progress will not change. (y/N) ", default=False):
            return

        cardsToReview = list(cards)
        updateSchedule = False
    else:
        print(ChatColor.paint(f"Due today: {plural(len(cardsToReview), 'card')}.", ChatColor.CYAN))

    print()
    mode = askReviewMode()
    if mode is None:
        return

    saveFailed = False

    def saveProgress() -> None:

        """
        Save after every answer. If the deck cannot be written, say so once and
        keep the session going, so the answers of this session are not lost.
        """

        nonlocal saveFailed

        if saveFailed:
            return

        try:
            cardDeck.saveDeck(cards, deckPath)
        except cardDeck.DeckSaveError as error:
            saveFailed = True
            print()
            print(ChatColor.paint(f"  {error}", ChatColor.RED))
            print(ChatColor.paint("  Your answers are kept for this session, but the deck file was not updated.", ChatColor.ORANGE))

    while True:
        summary = reviewCards.reviewCards(cardsToReview, mode, saveProgress=saveProgress, today=today, updateSchedule=updateSchedule)
        printSummary(summary)

        if saveFailed:
            print(ChatColor.paint("  Your progress was not saved. Fix the deck file problem, then try again.", ChatColor.ORANGE))
            return

        if not updateSchedule or summary["reviewed"] == 0:
            return

        remainingDue = cardDeck.getDueCards(cards, today)
        if len(remainingDue) == 0:
            return

        nextBatch = min(len(remainingDue), reviewCards.MAX_CARDS_PER_SESSION)
        print()
        if not askYesNo(f"Continue with the next {plural(nextBatch, 'card')}? (y/N) ", default=False):
            return

        cardsToReview = remainingDue
        print()


def askReviewMode() -> str | None:

    """
    Let the user choose a review mode. Returns None to go back to the menu.
    """

    modes = reviewCards.availableModes()
    nameWidth = max(len(reviewCards.MODE_NAMES[eachMode]) for eachMode in reviewCards.MODE_NAMES)

    print(ChatColor.paint("Review modes:", ChatColor.BOLD))
    print()

    for index, eachMode in enumerate(modes, start=1):
        name = ChatColor.paint(f"{reviewCards.MODE_NAMES[eachMode]:<{nameWidth}}", ChatColor.BOLD)
        description = ChatColor.paint(reviewCards.MODE_DESCRIPTIONS[eachMode], ChatColor.DARK_GRAY)
        print(f"  {index}. {name}   {description}")

    missingModes = []
    if not speechHelper.isSpeechAvailable():
        missingModes.append('Listening, Speaking: set ELEVENLABS_API_KEY and run  pip install ".[speech]"')
    if not genAITutor.isAIAvailable():
        missingModes.append("Sentence: set LLM_API_KEY")

    if len(missingModes) > 0:
        print()
        print(ChatColor.paint("  More modes:", ChatColor.DARK_GRAY))
        for eachNote in missingModes:
            print(terminalDisplay.wrapParagraph(eachNote, "    - ", prefixStyles=(ChatColor.DARK_GRAY,), textStyles=(ChatColor.DARK_GRAY,)))

    print()

    while True:
        choice = ask("Choose a mode (Enter = 1, q = back): ", ChatColor.YELLOW)

        if isQuit(choice):
            return None

        if choice == "":
            return modes[0]

        if choice.isdigit() and 1 <= int(choice) <= len(modes):
            return modes[int(choice) - 1]

        print(ChatColor.paint(f"Please choose a number from 1 to {len(modes)}.", ChatColor.ORANGE))


def printSummary(summary: dict) -> None:

    reviewed = summary["reviewed"]

    terminalDisplay.printHeading("Session finished")

    if reviewed == 0:
        print(ChatColor.paint("  No cards reviewed.", ChatColor.DARK_GRAY))
        return

    correct = summary["correct"]
    percent = round(correct * 100 / reviewed)

    labelWidth = 8
    print(terminalDisplay.labelLine("Reviewed", plural(reviewed, "card"), labelWidth))
    print(terminalDisplay.labelLine("Correct", ChatColor.paint(correct, ChatColor.GREEN), labelWidth))
    print(terminalDisplay.labelLine("Wrong", ChatColor.paint(summary["wrong"], ChatColor.RED), labelWidth))
    print(terminalDisplay.labelLine("Score", f"{percent}%", labelWidth))


# ---------- 4. View my deck ----------

def showDeck(cards: list[Card], deckPath: str) -> None:

    """
    List every card with its box, next review date, score and translation.
    Long decks are shown a page at a time, so the numbers stay readable.
    """

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty. Look up some words and add them first.", ChatColor.ORANGE))
        return

    today = date.today()
    dueCount = len(cardDeck.getDueCards(cards, today))

    terminalDisplay.printHeading(f"Your deck: {plural(len(cards), 'word')}, {dueCount} due today")

    sortedCards = cardDeck.sortByWord(cards)
    longestWord = max(len(eachCard.word) for eachCard in sortedCards)
    wordWidth = min(max(longestWord, len("Word")), MAX_DECK_WORD_WIDTH)
    numberWidth = max(len(str(len(sortedCards))), 1)

    # The numbers are the same as on the "Remove words" screen.
    header = f"  {'#':>{numberWidth}}  {'Word':<{wordWidth}}  Box  {'Next review':<11}  Score  Chinese"
    terminalWidth = terminalDisplay.screenWidth()
    narrow = terminalWidth < NARROW_DECK_WIDTH

    pages = []
    for start in range(0, len(sortedCards), DECK_PAGE_SIZE):
        pages.append(sortedCards[start:start + DECK_PAGE_SIZE])

    if len(pages) > 1:
        print(ChatColor.paint(f"  {DECK_PAGE_SIZE} words per page. Press Enter for the next page, q to go back.", ChatColor.DARK_GRAY))
        print()

    for pageIndex, pageCards in enumerate(pages, start=1):
        if not narrow:
            print(ChatColor.paint(header, ChatColor.BOLD))
            print(ChatColor.paint("  " + "─" * (len(header) - 2), ChatColor.DARK_GRAY))

        for offset, eachCard in enumerate(pageCards):
            index = (pageIndex - 1) * DECK_PAGE_SIZE + offset + 1
            isDue = leitnerScheduler.isDue(eachCard, today)
            score = f"{eachCard.correctCount}/{eachCard.timesReviewed()}"
            word = terminalDisplay.truncateText(eachCard.word, wordWidth)
            number = ChatColor.paint(f"{index:>{numberWidth}}", ChatColor.DARK_GRAY)

            if narrow:
                # A narrow terminal cannot line up a table, so each card gets its own lines instead.
                whenDue = "due now" if isDue else f"next {eachCard.nextReview}"
                line = f"  {number}  {ChatColor.paint(word, ChatColor.BOLD)}"
                line += ChatColor.paint(f"  ·  box {eachCard.box}  ·  {whenDue}  ·  {score}", ChatColor.DARK_GRAY)
                print(line)

                if eachCard.translation != "":
                    translationWidth = max(4, terminalWidth - 6)
                    print("      " + ChatColor.paint(terminalDisplay.truncateText(eachCard.translation, translationWidth), ChatColor.GREEN))
                continue

            if isDue:
                nextReview = ChatColor.paint(f"{'due now':<11}", ChatColor.ORANGE)
            else:
                nextReview = f"{eachCard.nextReview:<11}"

            # The translation is the last column, so it gets whatever room is left.
            translationWidth = max(4, terminalWidth - (numberWidth + wordWidth + 31))
            translation = terminalDisplay.truncateText(eachCard.translation, translationWidth)
            row = f"  {number}  {word:<{wordWidth}}  {eachCard.box:>3}  {nextReview}  {score:>5}  {translation}"
            print(row)

        print()

        if pageIndex < len(pages):
            answer = ask("Enter = next page, q = back: ", ChatColor.DARK_GRAY)
            if isQuit(answer):
                return

    print(ChatColor.paint(f"  Saved in: {deckPath}", ChatColor.DARK_GRAY))


# ---------- 8. Edit a card ----------

def editCard(cards: list[Card], deckPath: str) -> None:

    """
    Change a card that is already in the deck: its word, its Chinese translation or its meaning.
    Pressing Enter on a question keeps the current value; "-" clears that part.
    """

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty. Look up some words and add them first.", ChatColor.ORANGE))
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
            print(ChatColor.paint(f'"{newWord}" is already in your deck, so nothing was changed.', ChatColor.ORANGE))
            return

        card.word = newWord

    translation = ask("New Chinese (Enter = keep, - = clear): ", ChatColor.YELLOW)
    if isQuit(translation):
        return

    if translation == "-":
        card.translation = ""
    elif translation != "":
        card.translation = translation

    definition = ask("New meaning, one line (Enter = keep, - = clear): ", ChatColor.YELLOW)
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
        print(ChatColor.paint(f'  {error}', ChatColor.RED))
        print(ChatColor.paint("The change is in this session, but the deck file was not updated.", ChatColor.ORANGE))
        return

    print(ChatColor.paint(f'Updated "{card.word}".', ChatColor.GREEN))


# ---------- 9. Practise one word ----------

def practiseOneWord(cards: list[Card], deckPath: str) -> None:

    """
    Review a single card, whatever its next review date, in the mode the user picks.
    """

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty. Look up some words and add them first.", ChatColor.ORANGE))
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

    saveFailed = False

    def saveProgress() -> None:
        nonlocal saveFailed

        if saveFailed:
            return

        try:
            cardDeck.saveDeck(cards, deckPath)
        except cardDeck.DeckSaveError as error:
            saveFailed = True
            print()
            print(ChatColor.paint(f"  {error}", ChatColor.RED))
            print(ChatColor.paint("  Your answer is kept for this session, but the deck file was not updated.", ChatColor.ORANGE))

    summary = reviewCards.reviewCards([card], mode, saveProgress=saveProgress, today=date.today(), updateSchedule=True)
    printSummary(summary)

    if saveFailed:
        print(ChatColor.paint("  Your progress was not saved. Fix the deck file problem, then try again.", ChatColor.ORANGE))


# ---------- 6. Export deck to CSV ----------

def exportDeck(cards: list[Card], deckPath: str) -> None:

    """
    Save the deck as a CSV file for Excel, Google Sheets, Quizlet or Anki.
    """

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty, so there is nothing to export.", ChatColor.ORANGE))
        return

    answer = ask(f"Save as (Enter = {exportDeckToCSV.DEFAULT_EXPORT_FILE}, q = back): ", ChatColor.YELLOW)
    if isQuit(answer):
        return

    path = importVocabulary.cleanPath(answer) if answer != "" else exportDeckToCSV.DEFAULT_EXPORT_FILE

    if os.path.isdir(path):
        path = os.path.join(path, exportDeckToCSV.DEFAULT_EXPORT_FILE)

    if os.path.splitext(path)[1] == "":
        path += ".csv"

    if os.path.exists(path):
        if not askYesNo(f"{path} already exists. Replace it? (y/N) ", default=False):
            return

    try:
        count = exportDeckToCSV.exportDeckToCSV(cards, path)
    except OSError as error:
        print(ChatColor.paint(f"Could not save the file: {error}", ChatColor.RED))
        return

    print(ChatColor.paint(f"Exported {plural(count, 'word')} to {os.path.abspath(path)}", ChatColor.GREEN))


if __name__ == "__main__":
    main()
