from word_flashcard_vocab_learner import terminalDisplay


def test_wrap_paragraph_uses_hanging_indent():
    text = terminalDisplay.wrapParagraph("one two three four five six seven", "  1. ", width=26)

    assert text.splitlines() == [
        "  1. one two three four",
        "     five six seven",
    ]


def test_wrap_paragraph_keeps_long_words_whole():
    url = "https://example.com/a-very-long-address-that-cannot-be-split"
    assert terminalDisplay.wrapParagraph(url, "> ", width=30) == "> " + url


def test_wrap_paragraph_with_empty_text():
    assert terminalDisplay.wrapParagraph("", "  - ") == "  - "


def test_screen_width_is_limited(monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    assert terminalDisplay.screenWidth() == terminalDisplay.MAX_WIDTH

    monkeypatch.setenv("COLUMNS", "10")
    assert terminalDisplay.screenWidth() == terminalDisplay.MIN_WIDTH


def test_rule_with_title():
    line = terminalDisplay.rule("Card 1 of 2")

    assert line.startswith("─── Card 1 of 2 ")
    assert len(line) == terminalDisplay.MAX_RULE_WIDTH


def test_label_line_aligns_values():
    assert terminalDisplay.labelLine("Correct", 3, 9) == "  Correct    3"


def test_format_columns():
    items = ["1. cat", "2. dog", "3. ambiguous"]

    # Each column is as wide as the longest item ("3. ambiguous", 12) plus 3 spaces.
    assert terminalDisplay.formatColumns(items, width=40) == "  1. cat         2. dog\n  3. ambiguous"
    assert terminalDisplay.formatColumns([]) == ""


def test_clear_screen_does_nothing_when_not_a_terminal(capsys):
    terminalDisplay.clearScreen()
    assert capsys.readouterr().out == ""
