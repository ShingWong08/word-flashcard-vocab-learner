import random
import re
from collections.abc import Callable
from datetime import date

from word_flashcard_vocab_learner import (
    genAITutor,
    leitnerScheduler,
    speechHelper,
    terminalDisplay,
)
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.connectFreeDictionaryAPI import formatWordDefinition
from word_flashcard_vocab_learner.flashCard import Card
from word_flashcard_vocab_learner.userInput import ask, askYesNo, isQuit

MAX_CARDS_PER_SESSION = 20
MASK = "____"
INDENT = "  "

MODE_MEANING = "meaning"
MODE_SPELLING = "spelling"
MODE_LISTENING = "listening"
MODE_SPEAKING = "speaking"
MODE_SENTENCE = "sentence"

MODE_NAMES = {
    MODE_MEANING: "Meaning",
    MODE_SPELLING: "Spelling",
    MODE_LISTENING: "Listening",
    MODE_SPEAKING: "Speaking",
    MODE_SENTENCE: "Sentence",
}

MODE_DESCRIPTIONS = {
    MODE_MEANING: "See the word, recall what it means",
    MODE_SPELLING: "Read the clues, type the word",
    MODE_LISTENING: "Hear the word, type it",
    MODE_SPEAKING: "Read the clues, say the word",
    MODE_SENTENCE: "Write a sentence, get AI feedback",
}

# Curly quotes and dashes people paste from Word or a phone keyboard.
QUOTE_TRANSLATION = str.maketrans(
    {"’": "'", "‘": "'", "“": '"', "”": '"', "—": " ", "–": " "}
)

# Audio tags in a transcription, like "(laughs)" or "[noise]".
AUDIO_TAG = re.compile(r"\([^)]*\)|\[[^\]]*\]")
NOT_WORD_CHARACTER = re.compile(r"[^\w' ]")


# ---------- Answer checking ----------


def maskWord(text: str, word: str) -> str:
    """
    Hide the word (and forms like "cats" for "cat") in a sentence, so clues do not give
    the answer away.
    Example: maskWord("I have two cats.", "cat") -> "I have two ____."
    """

    # Only a regular ending may follow the word. "\w*" would also hide the start of a
    # longer word: "cat" must not blank "category".
    pattern = r"\b" + re.escape(word) + r"(?:s|es|ed|ing|er|est|'s)?(?![\w])"
    return re.sub(pattern, MASK, text, flags=re.IGNORECASE)


def makeHint(word: str) -> str:
    """
    Show the first letter and the length of the word.
    Example: "ambiguous" -> "a________ (9 letters)"
    """

    letterCount = sum(eachCharacter.isalpha() for eachCharacter in word)
    hint = word[:1] + "".join(
        "_" if eachCharacter.isalpha() else eachCharacter for eachCharacter in word[1:]
    )

    return f"{hint} ({letterCount} letters)"


def normalizeAnswer(text: str) -> str:
    """
    Make a typed answer easy to compare: lowercase, single spaces, no full stop at the
    end.
    """

    text = text.translate(QUOTE_TRANSLATION).replace("-", " ")
    return " ".join(text.split()).strip(".!?,;:\"'").casefold()


def isSpellingCorrect(answer: str, word: str) -> bool:
    return normalizeAnswer(answer) == normalizeAnswer(word)


def normalizeSpokenText(text: str) -> str:
    """
    Make a transcription easy to compare: remove audio tags like "(laughs)" or
    "[noise]",
    punctuation and hyphens, then lowercase.
    """

    text = AUDIO_TAG.sub(" ", text).replace("-", " ")
    text = NOT_WORD_CHARACTER.sub(" ", text)

    return " ".join(text.split()).casefold()


def isSpokenCorrect(transcription: str, word: str) -> bool:
    """
    Return True if the word was said, even inside a short phrase ("It's ambiguous."
    counts for "ambiguous").
    """

    target = normalizeSpokenText(word)

    return target != "" and f" {target} " in f" {normalizeSpokenText(transcription)} "


# ---------- Showing cards ----------


def formatTranslation(card: Card) -> str:
    """
    The "Chinese: ..." line, or "" if the card has no translation.
    """

    if card.translation == "":
        return ""

    return (
        INDENT
        + ChatColor.paint("Chinese: ", ChatColor.DARK_GRAY)
        + ChatColor.paint(card.translation, ChatColor.GREEN)
    )


def formatFront(card: Card) -> str:
    return INDENT + ChatColor.paint(card.word, ChatColor.BOLD, ChatColor.VIOLET)


def formatCardBack(card: Card) -> str:
    """
    The back of the card: numbered definitions with examples, then the Chinese
    translation.
    """

    if card.definitions:
        text = formatWordDefinition(
            {
                "word": card.word,
                "definitions": card.definitions,
                "examples": card.examples,
            }
        )
    else:
        text = INDENT + ChatColor.paint(
            "No meaning saved for this card. Press 8 on the main menu to add one.",
            ChatColor.ORANGE,
        )

    translationLine = formatTranslation(card)
    if translationLine != "":
        text += "\n\n" + translationLine

    return text


def formatClues(card: Card) -> str:
    """
    Clues for guessing the word: numbered definitions and one example each (with the
    word hidden),
    then the Chinese translation and a hint.
    """

    lines = [ChatColor.paint("Clues:", ChatColor.BOLD)]

    for index, eachDefinition in enumerate(card.definitions):
        number = f"{INDENT}{index + 1}. "

        lines.append("")
        lines.append(
            terminalDisplay.wrapParagraph(
                maskWord(eachDefinition, card.word),
                number,
                prefixStyles=(ChatColor.DARK_GRAY,),
            )
        )

        if index < len(card.examples) and card.examples[index]:
            lines.append(
                terminalDisplay.wrapParagraph(
                    maskWord(card.examples[index][0], card.word),
                    " " * len(number) + "> ",
                    prefixStyles=(ChatColor.DARK_GRAY,),
                    textStyles=(ChatColor.AQUA,),
                )
            )

    lines.append("")

    translationLine = formatTranslation(card)
    if translationLine != "":
        lines.append(translationLine)

    lines.append(
        INDENT + ChatColor.paint("Hint:    ", ChatColor.DARK_GRAY) + makeHint(card.word)
    )

    return "\n".join(lines)


def playSafely(word: str) -> bool:
    """
    Play the word's pronunciation. Prints the problem and returns False if it fails.
    """

    try:
        speechHelper.pronounce(word)
    except Exception as error:
        print(
            ChatColor.paint(f"Could not play the pronunciation: {error}", ChatColor.RED)
        )
        return False

    return True


# ---------- One question per mode ----------
# Each function returns True (right), False (wrong) or None (the user wants to stop).


def askMeaning(card: Card) -> bool | None:
    """
    Show the word, let the user think, flip the card, then let the user mark themselves.
    """

    print(formatFront(card))
    print()

    canPlay = speechHelper.isSpeechAvailable()
    if canPlay:
        promptText = "Press Enter to flip the card (p = play sound, q = stop): "
    else:
        promptText = "Press Enter to flip the card (q = stop): "

    while True:
        answer = ask(promptText, ChatColor.YELLOW)

        if isQuit(answer):
            return None

        if canPlay and answer.lower() == "p":
            playSafely(card.word)
            continue

        break

    print()
    print(formatCardBack(card))
    print()

    return askYesNo("Did you remember it? (y/n): ")


def askSpelling(card: Card) -> bool | None:
    """
    Show the clues and let the user type the word.
    """

    print(formatClues(card))
    print()

    answer = ask("Type the word (q = stop): ", ChatColor.YELLOW)

    if isQuit(answer):
        return None

    return isSpellingCorrect(answer, card.word)


def askListening(card: Card) -> bool | None:
    """
    Play the word and let the user type what they heard.
    """

    print(
        INDENT + ChatColor.paint("Listen and type the word you hear.", ChatColor.CYAN)
    )
    print()

    if not playSafely(card.word):
        return None

    while True:
        answer = ask("Your answer (r = replay, q = stop): ", ChatColor.YELLOW)

        if isQuit(answer):
            return None

        if answer.lower() != "r":
            return isSpellingCorrect(answer, card.word)

        playSafely(card.word)


def askSpeaking(card: Card) -> bool | None:
    """
    Show the clues and let the user say the word out loud.
    """

    print(formatClues(card))
    print()
    print(INDENT + ChatColor.paint("Say the word out loud.", ChatColor.CYAN))

    try:
        transcription = speechHelper.listenForWord()
    except Exception as error:
        print(
            ChatColor.paint(
                f"Could not record or transcribe your voice: {error}", ChatColor.RED
            )
        )
        return None

    print(
        ChatColor.paint("You said: ", ChatColor.BOLD)
        + ChatColor.paint(transcription, ChatColor.VIOLET)
    )

    return isSpokenCorrect(transcription, card.word)


def askSentence(card: Card) -> bool | None:
    """
    Let the user write a sentence with the word, and ask the AI tutor whether it is used
    correctly.
    """

    print(formatFront(card))
    print()

    firstDefinition = ""
    if card.definitions:
        firstDefinition = card.definitions[0]
        print(
            terminalDisplay.wrapParagraph(
                firstDefinition,
                INDENT + "Meaning: ",
                prefixStyles=(ChatColor.DARK_GRAY,),
            )
        )

    translationLine = formatTranslation(card)
    if translationLine != "":
        print(translationLine)

    print()

    while True:
        sentence = ask(
            f'Write a sentence using "{card.word}" (q = stop): ', ChatColor.YELLOW
        )

        if isQuit(sentence):
            return None

        if sentence != "":
            break

    print(ChatColor.paint("Checking your sentence...", ChatColor.BLUE))

    try:
        isCorrect, feedback = genAITutor.checkSentence(
            card.word, firstDefinition, sentence
        )
    except Exception as error:
        print(ChatColor.paint(f"Could not reach the AI tutor: {error}", ChatColor.RED))
        return None

    if feedback != "":
        print()

        # The first line starts with "Feedback: ", later lines line up under it.
        prefix = "Feedback: "
        for eachLine in feedback.splitlines():
            if eachLine.strip() == "":
                continue

            print(
                terminalDisplay.wrapParagraph(
                    eachLine.strip(), prefix, prefixStyles=(ChatColor.BOLD,)
                )
            )
            prefix = " " * len("Feedback: ")

        print()

    if isCorrect is None:
        return askYesNo("Count this as correct? (y/n): ")

    return isCorrect


ASK_FUNCTIONS = {
    MODE_MEANING: askMeaning,
    MODE_SPELLING: askSpelling,
    MODE_LISTENING: askListening,
    MODE_SPEAKING: askSpeaking,
    MODE_SENTENCE: askSentence,
}


def availableModes() -> list[str]:
    """
    Return the review modes that can be used right now.
    Listening and speaking need speech set up; sentence practice needs the AI tutor.
    """

    modes = [MODE_MEANING, MODE_SPELLING]

    if speechHelper.isSpeechAvailable():
        modes += [MODE_LISTENING, MODE_SPEAKING]

    if genAITutor.isAIAvailable():
        modes.append(MODE_SENTENCE)

    return modes


def showOutcome(card: Card, isCorrect: bool, mode: str) -> None:
    """
    Tell the user whether they were right. When they were wrong, show the answer.
    """

    print()

    if isCorrect:
        print(ChatColor.paint("Correct!", ChatColor.BOLD, ChatColor.GREEN))
        return

    if mode == MODE_MEANING:
        print(
            ChatColor.paint(
                "No problem, this card will come back soon.", ChatColor.ORANGE
            )
        )
        return

    print(
        ChatColor.paint(
            f'Not quite. The answer is "{card.word}".', ChatColor.BOLD, ChatColor.RED
        )
    )

    if mode != MODE_SENTENCE:
        print()
        print(formatCardBack(card))


# ---------- A whole review session ----------


def reviewCards(
    cards: list[Card],
    mode: str,
    saveProgress: Callable[[], None] | None = None,
    today: date | None = None,
    updateSchedule: bool = True,
    shuffle: bool = True,
    maxCards: int = MAX_CARDS_PER_SESSION,
) -> dict:
    """
    Review a list of cards in one mode.
    Cards answered wrongly are asked once more at the end of the session (only the first
    answer counts).

    Parameters:
        Mandatory:
            - cards (list[Card]): The cards to review.
            - mode (str): One of MODE_MEANING, MODE_SPELLING, MODE_LISTENING,
              MODE_SPEAKING, MODE_SENTENCE.
        Optional:
            - saveProgress (callable): Called after every scheduled answer, so progress
              is kept if the user stops.
            - today (date): The date to schedule from. Default is today.
            - updateSchedule (bool): False for extra practice that does not change boxes
              or review dates.
            - shuffle (bool): Review the cards in random order.
            - maxCards (int): Maximum number of cards in one session.
    Returns:
        dict: {"reviewed": int, "correct": int, "wrong": int, "stopped": bool}
    """

    if mode not in ASK_FUNCTIONS:
        raise ValueError(f"Unknown review mode: {mode}")

    if today is None:
        today = date.today()

    selectedCards = list(cards)
    if shuffle:
        random.shuffle(selectedCards)
    selectedCards = selectedCards[:maxCards]

    # (card, isRetry): a card answered wrongly is added to the end once more.
    queue = [(eachCard, False) for eachCard in selectedCards]
    askCard = ASK_FUNCTIONS[mode]
    summary = {"reviewed": 0, "correct": 0, "wrong": 0, "stopped": False}

    # Cards added to the end of the queue while it is being read are still reached by
    # this loop.
    for card, isRetry in queue:
        if isRetry:
            title = "Try again"
        else:
            title = f"Card {summary['reviewed'] + 1} of {len(selectedCards)}"

        terminalDisplay.printHeading(title)

        isCorrect = askCard(card)

        if isCorrect is None:
            summary["stopped"] = True
            break

        showOutcome(card, isCorrect, mode)

        if isRetry:
            continue

        summary["reviewed"] += 1

        if isCorrect:
            summary["correct"] += 1
        else:
            summary["wrong"] += 1
            queue.append((card, True))

        if updateSchedule:
            leitnerScheduler.recordAnswer(card, isCorrect, today)
            whenNext = leitnerScheduler.describeNextReview(card, today)
            print(
                ChatColor.paint(
                    f"Box {card.box} · next review {whenNext}", ChatColor.DARK_GRAY
                )
            )

            if saveProgress is not None:
                saveProgress()

    return summary
