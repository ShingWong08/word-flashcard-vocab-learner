"""A vocabulary flashcard toolkit that turns your own reading into a study deck.

Public API::

    from word_flashcard_vocab_learner import Card, Deck, review

    deck = Deck([Card("ambiguous", level="C1")])
    review(deck.cards[0], 3)
"""

from __future__ import annotations

from .models import LEVEL_RANK, LEVELS, Card, Deck
from .srs import interval_for, retention, review

__version__ = "0.2.0"

__all__ = [
    "Card",
    "Deck",
    "LEVELS",
    "LEVEL_RANK",
    "__version__",
    "interval_for",
    "retention",
    "review",
]
