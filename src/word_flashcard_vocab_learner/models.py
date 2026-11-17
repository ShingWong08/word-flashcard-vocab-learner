"""Core data model: a vocabulary card and a deck of cards.

Everything here is standard library only, so the package installs and imports
cleanly on a bare JupyterHub image.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Iterator

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
LEVEL_RANK = {level: i for i, level in enumerate(LEVELS)}


def _coerce_level(level: str) -> str:
    normalized = (level or "B1").strip().upper()
    if normalized not in LEVEL_RANK:
        raise ValueError(f"unknown CEFR level {level!r}; expected one of {LEVELS}")
    return normalized


@dataclass
class Card:
    """One vocabulary item plus its scheduling state."""

    word: str
    level: str = "B1"
    pos: str | None = None
    definition: str | None = None
    example: str | None = None
    translation: str | None = None
    source: str | None = None
    stability: float = 0.0
    difficulty: float = 5.0
    reps: int = 0
    lapses: int = 0
    due: str | None = None
    last_review: str | None = None

    def __post_init__(self) -> None:
        self.word = (self.word or "").strip()
        if not self.word:
            raise ValueError("card word cannot be empty")
        self.level = _coerce_level(self.level)

    @property
    def is_new(self) -> bool:
        return self.reps == 0

    def due_date(self) -> date | None:
        return date.fromisoformat(self.due) if self.due else None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Card":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Deck:
    """An ordered collection of cards, serialisable to JSON."""

    cards: list[Card] = field(default_factory=list)
    name: str = "deck"

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and self.get(word) is not None

    def get(self, word: str) -> Card | None:
        key = word.strip().lower()
        for card in self.cards:
            if card.word.lower() == key:
                return card
        return None

    def add(self, card: Card) -> Card:
        """Add a card, or return the existing card with the same word."""
        existing = self.get(card.word)
        if existing is not None:
            return existing
        self.cards.append(card)
        return card

    def extend(self, cards: Iterable[Card]) -> "Deck":
        for card in cards:
            self.add(card)
        return self

    def merge(self, other: "Deck") -> "Deck":
        """Merge another deck in; scheduling state of the newer card wins."""
        for card in other:
            existing = self.get(card.word)
            if existing is None:
                self.cards.append(card)
            elif card.reps >= existing.reps:
                for f in fields(Card):
                    setattr(existing, f.name, getattr(card, f.name))
        return self

    def due(self, on: date | None = None) -> list[Card]:
        """Cards that should be reviewed today (new cards always count)."""
        on = on or date.today()
        return [c for c in self.cards if c.is_new or (c.due_date() or on) <= on]

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"name": self.name, "cards": [c.to_dict() for c in self.cards]}
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "Deck":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            cards=[Card.from_dict(item) for item in data.get("cards", [])],
            name=data.get("name", "deck"),
        )

    def stats(self, on: date | None = None) -> dict[str, Any]:
        on = on or date.today()
        by_level = {level: 0 for level in LEVELS}
        for card in self.cards:
            by_level[card.level] += 1
        learned = [c for c in self.cards if not c.is_new]
        return {
            "total": len(self.cards),
            "by_level": by_level,
            "new": len(self.cards) - len(learned),
            "due_today": len(self.due(on)),
            "learned": len(learned),
        }
