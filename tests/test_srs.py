"""Tests for the FSRS-lite scheduler."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from word_flashcard_vocab_learner import Card, interval_for, retention, review

TODAY = date(2026, 11, 17)


def test_retention_is_one_at_zero_days():
    assert retention(0, 5.0) == 1.0


def test_retention_is_ninety_percent_at_one_stability():
    assert retention(1.0, 1.0) == pytest.approx(0.9)


def test_retention_decreases_monotonically():
    values = [retention(d, 5.0) for d in range(0, 30)]
    assert all(a >= b for a, b in zip(values, values[1:]))


def test_interval_round_trips_through_retention():
    for stability in (0.5, 1.0, 10.0, 60.0):
        days = interval_for(stability)
        assert retention(days, stability) == pytest.approx(0.9, abs=1e-6)


def test_good_rating_grows_stability_and_sets_due():
    card = Card("peer")
    review(card, 3, today=TODAY)
    assert card.reps == 1
    assert card.stability > 1.0
    assert card.last_review == TODAY.isoformat()
    assert card.due_date() > TODAY


def test_easy_outgrows_good():
    good, easy = Card("peer"), Card("peer")
    review(good, 3, today=TODAY)
    review(easy, 4, today=TODAY)
    assert easy.stability > good.stability


def test_again_shrinks_stability_and_counts_lapse():
    card = Card("peer", reps=1, stability=20.0)
    review(card, 1, today=TODAY)
    assert card.stability == pytest.approx(4.0)
    assert card.lapses == 1
    assert card.due_date() == TODAY + timedelta(days=4)


def test_difficulty_stays_in_bounds():
    card = Card("peer", difficulty=1.2)
    for _ in range(30):
        review(card, 1, today=TODAY)
    assert card.difficulty <= 10.0
    for _ in range(60):
        review(card, 4, today=TODAY)
    assert card.difficulty >= 1.0


def test_invalid_rating_raises():
    with pytest.raises(ValueError):
        review(Card("peer"), 0)
    with pytest.raises(ValueError):
        review(Card("peer"), 5)


def test_extreme_reviews_stay_in_date_range():
    card = Card("peer")
    for _ in range(200):
        review(card, 4, today=TODAY)
    assert card.due_date() is not None
    assert card.stability <= 36500.0
