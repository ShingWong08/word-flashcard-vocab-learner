import os
import shutil
import sys
import textwrap

from word_flashcard_vocab_learner.chatColor import ChatColor

MIN_WIDTH = 40
MAX_WIDTH = 100
MAX_RULE_WIDTH = 60
MIN_TEXT_WIDTH = 20
MAX_WORD_COLUMN_WIDTH = 24


def plural(count: int, noun: str) -> str:
    """
    Put a count in front of a noun, and add "s" unless the count is exactly 1.
    Example: plural(1, "word") -> "1 word", plural(3, "word") -> "3 words"

    Parameters:
        Mandatory:
            - count (int): How many there are.
            - noun (str): The singular form of the noun, e.g. "word" or "card". It has
              to be a noun whose plural just adds "s".
    Returns:
        str: The count and the noun, e.g. "0 words", "1 word", "2 words".
    """

    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def screenWidth() -> int:
    """
    Return how many characters fit on one line, between MIN_WIDTH and MAX_WIDTH.
    Very long lines are hard to read, so text is never wider than MAX_WIDTH even on a
    wide screen.
    """

    columns = shutil.get_terminal_size((80, 24)).columns
    return max(MIN_WIDTH, min(columns, MAX_WIDTH))


def wrapParagraph(
    text: str,
    prefix: str = "",
    prefixStyles: tuple = (),
    textStyles: tuple = (),
    width: int | None = None,
) -> str:
    """
    Wrap text so every line fits on the screen.
    The first line starts with prefix; the following lines are indented to line up under
    the text.

    Example (prefix "  1. "):
        "  1. The elongated curved tropical fruit of a banana plant, which grows"
        "     in bunches and has a creamy flesh and a smooth skin."

    Parameters:
        Mandatory:
            - text (str): The plain text to wrap.
        Optional:
            - prefix (str): Text before the first line, e.g. "  1. " or "     > ".
            - prefixStyles (tuple): ChatColor styles for the prefix.
            - textStyles (tuple): ChatColor styles for the text.
            - width (int | None): Line width. Default is the screen width.
    Returns:
        str: The wrapped lines joined with newlines. There is always at least one line,
        even for empty text.
    """

    if width is None:
        width = screenWidth()

    lines = textwrap.wrap(
        text,
        width=max(MIN_TEXT_WIDTH, width - len(prefix)),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]

    indent = " " * len(prefix)
    result = [
        ChatColor.paint(prefix, *prefixStyles) + ChatColor.paint(lines[0], *textStyles)
    ]
    result += [
        indent + ChatColor.paint(eachLine, *textStyles) for eachLine in lines[1:]
    ]

    return "\n".join(result)


def rule(title: str = "") -> str:
    """
    A horizontal line, optionally with a title, used to separate sections.
    The line is as wide as the screen, but never wider than MAX_RULE_WIDTH characters.
    Example: "─── Card 1 of 2 ──────────────────────"

    Parameters:
        Optional:
            - title (str): Text shown near the start of the line, in bold cyan.
              Default: "" (a plain line without a title).
    Returns:
        str: The line, in color when colors are turned on.
    """

    width = min(screenWidth(), MAX_RULE_WIDTH)

    if title == "":
        return ChatColor.paint("─" * width, ChatColor.DARK_GRAY)

    titleText = f" {title} "
    rightLength = max(3, width - 3 - len(titleText))

    return (
        ChatColor.paint("───", ChatColor.DARK_GRAY)
        + ChatColor.paint(titleText, ChatColor.BOLD, ChatColor.CYAN)
        + ChatColor.paint("─" * rightLength, ChatColor.DARK_GRAY)
    )


def printHeading(title: str) -> None:
    """
    Print a blank line, then a titled rule and another blank line, to start a new
    section of the screen (see rule).

    Parameters:
        Mandatory:
            - title (str): The section title, e.g. "Main menu" or "Card 1 of 20".
    """

    print()
    print(rule(title))
    print()


def labelLine(label: str, value: object, labelWidth: int, indent: str = "  ") -> str:
    """
    A "label   value" line for lists where all values line up, such as the progress
    screen. The label is shown in dark gray.
    Example: labelLine("Correct", 3, 9) -> "  Correct    3"

    Parameters:
        Mandatory:
            - label (str): The name on the left, e.g. "Correct".
            - value (object): The value on the right. Anything that is not a string is
              turned into one with str().
            - labelWidth (int): How many characters the label column takes. Use the
              same width, at least as long as the longest label, for every line of a
              list.
        Optional:
            - indent (str): Text before the label. Default: "  " (two spaces).
    Returns:
        str: The finished line.
    """

    return (
        indent
        + ChatColor.paint(f"{label:<{labelWidth}}", ChatColor.DARK_GRAY)
        + "  "
        + str(value)
    )


def truncateText(text: str, width: int) -> str:
    """
    Shorten text so it fits a column. Long words get "…", so the columns next to them
    stay lined up.

    Parameters:
        Mandatory:
            - text (str): The text to fit.
            - width (int): The most characters the text may take. Below 2 there is no
              room for a letter and "…", so the text is then returned unchanged.
    Returns:
        str: The text unchanged if it fits, otherwise its first width - 1 characters
        followed by "…".
    """

    if width < 2 or len(text) <= width:
        return text

    return text[: width - 1] + "…"


def formatColumns(
    items: list[str], indent: str = "  ", width: int | None = None
) -> str:
    """
    Lay out short items (e.g. numbered words) in as many columns as fit on the screen,
    filling each row from left to right. Every column is as wide as the longest item
    plus 3 spaces.

    Parameters:
        Mandatory:
            - items (list[str]): The items, in the order to show them.
        Optional:
            - indent (str): Text at the start of every row. Default: "  ".
            - width (int | None): The width of a row in characters.
              Default: None (the screen width, see screenWidth).
    Returns:
        str: The rows joined with newlines, or "" when there are no items.
    """

    if not items:
        return ""

    if width is None:
        width = screenWidth()

    columnWidth = max(map(len, items)) + 3
    columnCount = max(1, (width - len(indent)) // columnWidth)

    rows = (
        items[start : start + columnCount]
        for start in range(0, len(items), columnCount)
    )

    return "\n".join(
        indent + "".join(f"{eachItem:<{columnWidth}}" for eachItem in eachRow).rstrip()
        for eachRow in rows
    )


def clearScreen() -> None:
    """
    Clear the terminal. Does nothing when output is not a terminal (e.g. in tests).
    """

    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return

    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[3J\033[H", end="", flush=True)
