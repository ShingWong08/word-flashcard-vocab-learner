from word_flashcard_vocab_learner import terminalDisplay


def testWrapParagraphUsesHangingIndent():
    text = terminalDisplay.wrapParagraph(
        "one two three four five six seven", "  1. ", width=26
    )

    assert text.splitlines() == [
        "  1. one two three four",
        "     five six seven",
    ]


def testWrapParagraphKeepsLongWordsWhole():
    url = "https://example.com/a-very-long-address-that-cannot-be-split"
    assert terminalDisplay.wrapParagraph(url, "> ", width=30) == "> " + url


def testWrapParagraphWithEmptyText():
    assert terminalDisplay.wrapParagraph("", "  - ") == "  - "


def testScreenWidthIsLimited(monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    assert terminalDisplay.screenWidth() == terminalDisplay.MAX_WIDTH

    monkeypatch.setenv("COLUMNS", "10")
    assert terminalDisplay.screenWidth() == terminalDisplay.MIN_WIDTH


def testRuleWithTitle():
    line = terminalDisplay.rule("Card 1 of 2")

    assert line.startswith("─── Card 1 of 2 ")
    assert len(line) == terminalDisplay.MAX_RULE_WIDTH


def testLabelLineAlignsValues():
    assert terminalDisplay.labelLine("Correct", 3, 9) == "  Correct    3"


def testFormatColumns():
    items = ["1. cat", "2. dog", "3. ambiguous"]

    # Each column is as wide as the longest item ("3. ambiguous", 12) plus 3 spaces.
    assert (
        terminalDisplay.formatColumns(items, width=40)
        == "  1. cat         2. dog\n  3. ambiguous"
    )
    assert terminalDisplay.formatColumns([]) == ""


def testClearScreenDoesNothingWhenNotATerminal(capsys):
    terminalDisplay.clearScreen()
    assert capsys.readouterr().out == ""
