"""A compact FSRS-style scheduler implemented with the standard library.

The forgetting curve is the FSRS-4.5 shape with fixed constants:

    R(t, S) = (1 + (19/81) * t / S) ** -0.5

At the default target retention of 0.9 the next interval is approximately the
stability ``S``, which makes the scheduler easy to reason about and to test.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import Card

FACTOR = 19 / 81
DECAY = -0.5
TARGET_RETENTION = 0.9
MIN_STABILITY = 0.1
MAX_STABILITY = 36500.0
MAX_INTERVAL_DAYS = 3650
MAX_DIFFICULTY = 10.0
DEFAULT_STABILITY = 1.0
DEFAULT_DIFFICULTY = 5.0
RATINGS = (1, 2, 3, 4)


def retention(days: float, stability: float) -> float:
    """Probability of recall after ``days`` given memory ``stability``."""
    if days <= 0:
        return 1.0
    if stability <= 0:
        return 0.0
    return float((1 + FACTOR * days / stability) ** DECAY)


def interval_for(stability: float, target: float = TARGET_RETENTION) -> float:
    """Number of days until recall probability decays to ``target``."""
    if stability <= 0:
        return 1.0
    return float((target ** (1 / DECAY) - 1) * stability / FACTOR)


def review(card: Card, rating: int, today: date | None = None) -> Card:
    """Apply a review rating (1 Again, 2 Hard, 3 Good, 4 Easy) to ``card``."""
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ValueError(f"rating must be one of {RATINGS}, got {rating!r}") from None
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {RATINGS}, got {rating!r}")

    today = today or date.today()
    if card.stability <= 0:
        card.stability = DEFAULT_STABILITY
    if card.difficulty <= 0:
        card.difficulty = DEFAULT_DIFFICULTY

    if rating == 1:
        card.stability = max(MIN_STABILITY, card.stability * 0.2)
        card.difficulty = min(MAX_DIFFICULTY, card.difficulty + 0.8)
        card.lapses += 1
    elif rating == 2:
        card.stability *= 1.2
        card.difficulty = min(MAX_DIFFICULTY, card.difficulty + 0.15)
    elif rating == 3:
        card.stability *= 1 + 0.9 * (MAX_DIFFICULTY + 1 - card.difficulty) / 10
    else:
        card.stability *= 1 + 1.3 * (MAX_DIFFICULTY + 1 - card.difficulty) / 10
        card.difficulty = max(1.0, card.difficulty - 0.3)

    card.stability = min(MAX_STABILITY, card.stability)
    card.reps += 1
    card.last_review = today.isoformat()
    interval = min(MAX_INTERVAL_DAYS, max(1, round(interval_for(card.stability))))
    card.due = (today + timedelta(days=interval)).isoformat()
    return card
