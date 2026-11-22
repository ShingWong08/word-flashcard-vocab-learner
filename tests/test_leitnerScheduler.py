from datetime import date

from word_flashcard_vocab_learner import leitnerScheduler
from word_flashcard_vocab_learner.flashCard import Card

TODAY = date(2026, 11, 18)


def makeCard(box=1, nextReview="2026-11-18"):
    return Card("cat", ["a pet"], box=box, nextReview=nextReview)


def testRightAnswerMovesCardUpAndWaitsLonger():
    card = makeCard(box=1)
    leitnerScheduler.recordAnswer(card, True, TODAY)

    assert card.box == 2
    assert card.nextReview == "2026-11-20"
    assert card.correctCount == 1


def testWrongAnswerSendsCardBackToBoxOne():
    card = makeCard(box=4)
    leitnerScheduler.recordAnswer(card, False, TODAY)

    assert card.box == 1
    assert card.nextReview == "2026-11-19"
    assert card.wrongCount == 1


def testBoxNeverGoesAboveMax():
    card = makeCard(box=5)
    leitnerScheduler.recordAnswer(card, True, TODAY)

    assert card.box == 5
    assert card.nextReview == "2026-12-02"


def testOutOfRangeBoxIsClamped():
    card = makeCard(box=99)
    leitnerScheduler.recordAnswer(card, True, TODAY)
    assert card.box == 5

    card = makeCard(box=0)
    leitnerScheduler.recordAnswer(card, True, TODAY)
    assert card.box == 2


def testIsDue():
    assert leitnerScheduler.isDue(makeCard(nextReview="2026-11-18"), TODAY) is True
    assert leitnerScheduler.isDue(makeCard(nextReview="2026-11-19"), TODAY) is False
    assert leitnerScheduler.isDue(makeCard(nextReview="not a date"), TODAY) is True


def testDescribeNextReview():
    assert (
        leitnerScheduler.describeNextReview(makeCard(nextReview="2026-11-18"), TODAY)
        == "today"
    )
    assert (
        leitnerScheduler.describeNextReview(makeCard(nextReview="2026-11-19"), TODAY)
        == "tomorrow"
    )
    assert (
        leitnerScheduler.describeNextReview(makeCard(nextReview="2026-11-22"), TODAY)
        == "in 4 days"
    )
