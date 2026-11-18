"""A lightweight CLI flashcard tool for vocabulary learning and review."""

__version__ = "0.1.2"

import os

import requests

from word_flashcard_vocab_learner import connectFreeDictionaryAPI
from word_flashcard_vocab_learner.chatColor import ChatColor


QUIT_COMMANDS = ["q", "quit", "exit"]
YES_ANSWERS = ["y", "yes"]


def main() -> None:

    """
    Run the interactive word lookup: ask for a word, show its definitions,
    and repeat until the user quits.
    """

    printWelcome()

    while True:
        word = askForWord()

        if word is None:
            break

        if word.lower() in QUIT_COMMANDS:
            break

        if word == "":
            continue

        showDefinitions(word)
        print()

    print(ChatColor.paint("Goodbye!", ChatColor.BOLD, ChatColor.CYAN))


def printWelcome() -> None:
    print(ChatColor.paint("Welcome to the Word Flashcard Vocab Learner!", ChatColor.BOLD, ChatColor.CYAN))
    print("This package helps you learn English vocabulary more easily!")
    print(ChatColor.paint("Type an English word to look it up, or 'q' to quit.\n", ChatColor.DARK_GRAY))


def askForWord() -> str | None:

    """
    Ask the user for a word. Returns None if the user presses Ctrl+C or Ctrl+Z / Ctrl+D.
    """

    try:
        answer = input(ChatColor.paint("Word: ", ChatColor.BOLD, ChatColor.YELLOW))
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    return answer.strip()


def showDefinitions(word: str) -> None:

    """
    Look up the word and print its definitions.
    If the word was found and speech is set up, offer to play its pronunciation.
    """

    try:
        result = connectFreeDictionaryAPI.getWordDefinition(word)
    except requests.RequestException as error:
        print(ChatColor.paint(f"Could not reach the dictionary: {error}", ChatColor.RED))
        return

    print(result)

    wordWasFound = len(result) != ""
    speechIsSetUp = bool(os.environ.get("ELEVENLABS_API_KEY"))

    if wordWasFound and speechIsSetUp:
        offerPronunciation(word)


def offerPronunciation(word: str) -> None:

    """
    Ask whether to play the word's pronunciation, and play it if the user says yes.
    """

    answer = input(ChatColor.paint("Play pronunciation? (y/N) ", ChatColor.YELLOW))

    if answer.strip().lower() not in YES_ANSWERS:
        return

    try:
        from word_flashcard_vocab_learner.textToSpeech import textToSpeech
    except ImportError:
        print(ChatColor.paint("Speech support is not installed. Run: pip install .[speech]", ChatColor.ORANGE))
        return

    try:
        textToSpeech(word)
    except Exception as error:
        print(ChatColor.paint(f"Could not play pronunciation: {error}", ChatColor.RED))


if __name__ == "__main__":
    main()
