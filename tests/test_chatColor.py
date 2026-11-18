from word_flashcard_vocab_learner.chatColor import ChatColor


def test_paint_adds_styles_and_reset_when_enabled(monkeypatch):
    monkeypatch.setattr(ChatColor, "isEnabled", staticmethod(lambda: True))
    assert ChatColor.paint("hi", ChatColor.BOLD, ChatColor.GREEN) == "\033[1m\033[92mhi\033[0m"


def test_paint_returns_plain_text_when_disabled(monkeypatch):
    monkeypatch.setattr(ChatColor, "isEnabled", staticmethod(lambda: False))
    assert ChatColor.paint("hi", ChatColor.RED) == "hi"


def test_paint_without_styles_returns_plain_text(monkeypatch):
    monkeypatch.setattr(ChatColor, "isEnabled", staticmethod(lambda: True))
    assert ChatColor.paint(42) == "42"


def test_no_color_env_disables_colors(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert ChatColor.isEnabled() is False


def test_not_a_terminal_disables_colors(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    # capsys replaces stdout with a non-terminal stream
    assert ChatColor.isEnabled() is False
