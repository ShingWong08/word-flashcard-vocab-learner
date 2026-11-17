"""Tests for the card and deck data model."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from word_flashcard_vocab_learner import Card, Deck
from word_flashcard_vocab_learner.models import LEVELS


def test_card_defaults_and_normalisation():
    card = Card("  Ambiguity ", level="c1")
    assert card.word == "Ambiguity"
    assert card.level == "C1"
    assert card.is_new is True
    assert card.stability == 0.0


def test_card_rejects_bad_level_and_empty_word():
    with pytest.raises(ValueError):
        Card("word", level="Z9")
    with pytest.raises(ValueError):
        Card("   ")


def test_card_dict_roundtrip_ignores_unknown_keys():
    card = Card("peer", level="B2", definition="an equal", example="Peer review.")
    restored = Card.from_dict({**card.to_dict(), "legacy_field": 1})
    assert restored == card


def test_deck_add_is_case_insensitive_and_idempotent():
    deck = Deck()
    first = deck.add(Card("Peer"))
    second = deck.add(Card("peer"))
    assert first is second
    assert len(deck) == 1
    assert "PEER" in deck


def test_deck_merge_keeps_most_practised_state():
    old = Deck([Card("peer", reps=3, stability=9.0)])
    new = Deck([Card("peer", reps=1, stability=2.0), Card("coherent")])
    old.merge(new)
    assert len(old) == 2
    assert old.get("peer").stability == 9.0


def test_deck_due_includes_new_cards_and_due_ones():
    today = date(2026, 11, 17)
    deck = Deck(
        [
            Card("new"),
            Card("due", reps=2, due=(today - timedelta(days=1)).isoformat()),
            Card("later", reps=2, due=(today + timedelta(days=3)).isoformat()),
        ]
    )
    words = {c.word for c in deck.due(today)}
    assert words == {"new", "due"}


def test_deck_save_and_load(tmp_path):
    today = date(2026, 11, 17)
    deck = Deck([Card("peer", level="B2", translation="同儕", reps=2,
                      due=today.isoformat())], name="demo")
    path = deck.save(tmp_path / "nested" / "deck.json")

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["cards"][0]["translation"] == "同儕"

    loaded = Deck.load(path)
    assert loaded.name == "demo"
    assert loaded.cards == deck.cards


def test_deck_stats_counts_levels():
    deck = Deck([Card("a", level="B1"), Card("b", level="C1"),
                 Card("c", level="C1", reps=4, due=date(2026, 11, 18).isoformat())])
    stats = deck.stats(date(2026, 11, 17))
    assert stats["total"] == 3
    assert stats["by_level"]["C1"] == 2
    assert stats["by_level"]["A1"] == 0
    assert stats["learned"] == 1
    assert stats["new"] == 2
    assert set(stats["by_level"]) == set(LEVELS)
