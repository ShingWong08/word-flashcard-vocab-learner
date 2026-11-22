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
    Example: plural(1, "word") -> "1 word", plural(3, "word") -> "3 words"
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
    Example: "─── Card 1 of 2 ──────────────────────"
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
    Print a blank line, then a titled rule and another blank line.
    """

    print()
    print(rule(title))
    print()


def labelLine(label: str, value: object, labelWidth: int, indent: str = "  ") -> str:
    """
    A "label   value" line where all values line up.
    Example: labelLine("Correct", 3, 9) -> "  Correct    3"
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
    """

    if width < 2 or len(text) <= width:
        return text

    return text[: width - 1] + "…"


def formatColumns(
    items: list[str], indent: str = "  ", width: int | None = None
) -> str:
    """
    Lay out short items (e.g. numbered words) in as many columns as fit on the screen,
    filling each row from left to right.
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
