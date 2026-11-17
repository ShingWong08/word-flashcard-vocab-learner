"""Tests for the CLI surface and import purity."""

from __future__ import annotations

import importlib
import socket
import sys

import pytest

from word_flashcard_vocab_learner import __version__, cli


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_exits_cleanly(capsys):
    assert cli.main([]) == 0
    assert "word-flashcard" in capsys.readouterr().out


def test_import_does_no_io(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise AssertionError("import must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", boom, raising=False)
    monkeypatch.setattr(socket, "create_connection", boom, raising=False)

    for name in [m for m in sys.modules if m.startswith("word_flashcard_vocab_learner")]:
        del sys.modules[name]

    importlib.import_module("word_flashcard_vocab_learner")
    importlib.import_module("word_flashcard_vocab_learner.cli")

    assert capsys.readouterr().out == ""
