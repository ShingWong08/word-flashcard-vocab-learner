from word_flashcard_vocab_learner.chatColor import ChatColor


def testPaintAddsStylesAndResetWhenEnabled(monkeypatch):
    monkeypatch.setattr(ChatColor, "isEnabled", staticmethod(lambda: True))
    assert (
        ChatColor.paint("hi", ChatColor.BOLD, ChatColor.GREEN)
        == "\033[1m\033[92mhi\033[0m"
    )


def testPaintReturnsPlainTextWhenDisabled(monkeypatch):
    monkeypatch.setattr(ChatColor, "isEnabled", staticmethod(lambda: False))
    assert ChatColor.paint("hi", ChatColor.RED) == "hi"


def testPaintWithoutStylesReturnsPlainText(monkeypatch):
    monkeypatch.setattr(ChatColor, "isEnabled", staticmethod(lambda: True))
    assert ChatColor.paint(42) == "42"


def testNoColorEnvDisablesColors(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert ChatColor.isEnabled() is False


def testNotATerminalDisablesColors(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    # capsys replaces stdout with a non-terminal stream
    assert ChatColor.isEnabled() is False
