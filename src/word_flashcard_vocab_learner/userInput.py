from word_flashcard_vocab_learner.chatColor import ChatColor

BYTE_ORDER_MARK = "﻿"

QUIT_COMMANDS = ["q", "quit", "exit"]
YES_ANSWERS = ["y", "yes"]
NO_ANSWERS = ["n", "no"]


def ask(promptText: str, *styles: str) -> str | None:
    """
    Show a prompt and return what the user typed, with spaces trimmed.
    A byte order mark (added by Windows when input is piped from PowerShell or a UTF-8
    file) is removed.

    Parameters:
        Mandatory:
            - promptText (str): The text shown before the cursor, e.g. "Word: ".
        Optional:
            - styles (str): ChatColor codes for the prompt, e.g. ChatColor.YELLOW.
              Default: none (plain text).
    Returns:
        str | None: What the user typed, without spaces at the start and the end (it
        can be "" when the user only pressed Enter). None if the user pressed Ctrl+C,
        or ended the input with Ctrl+Z (Windows) / Ctrl+D (macOS, Linux).
    """

    try:
        answer = input(ChatColor.paint(promptText, *styles))
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    return answer.replace(BYTE_ORDER_MARK, "").strip()


def isQuit(answer: str | None) -> bool:
    """
    Tell whether an answer means "stop": q, quit or exit (in any upper / lower case),
    or None, which ask() returns for Ctrl+C or Ctrl+Z / Ctrl+D.

    Parameters:
        Mandatory:
            - answer (str | None): What ask() returned.
    Returns:
        bool: True if the user wants to stop, otherwise False.
    """

    return answer is None or answer.lower() in QUIT_COMMANDS


def askYesNo(promptText: str, default: bool | None = None) -> bool | None:
    """
    Ask a yes / no question until the user gives a valid answer.
    Parameters:
        Mandatory:
            - promptText (str): The question to show.
        Optional:
            - default (bool | None): Answer used when the user just presses Enter.
              If None, an empty answer just asks again (without a warning, so holding
              Enter does not fill the screen).
    Returns:
        True for yes, False for no, None if the user wants to stop (q, Ctrl+C, Ctrl+Z /
        Ctrl+D).
    """

    while True:
        answer = ask(promptText, ChatColor.YELLOW)

        if isQuit(answer):
            return None

        lowered = answer.lower()

        if lowered in YES_ANSWERS:
            return True

        if lowered in NO_ANSWERS:
            return False

        if lowered == "":
            if default is not None:
                return default
            continue

        print(ChatColor.paint("Please answer y or n.", ChatColor.ORANGE))
