from datetime import date, timedelta

from word_flashcard_vocab_learner.flashCard import Card


MIN_BOX = 1
MAX_BOX = 5

# Leitner system: days to wait before the next review, for each box.
# A right answer moves the card up one box, a wrong answer sends it back to box 1.
INTERVAL_DAYS = {
    1: 1,
    2: 2,
    3: 4,
    4: 7,
    5: 14,
}


def clampBox(box: int) -> int:

    """
    Keep a box number between MIN_BOX and MAX_BOX (in case the deck file was edited by hand).
    """

    return max(MIN_BOX, min(box, MAX_BOX))


def recordAnswer(card: Card, isCorrect: bool, today: date) -> None:

    """
    Update a card after it has been reviewed.
    Right answer: move up one box (at most MAX_BOX) and wait longer.
    Wrong answer: go back to box 1 and come back tomorrow.
    """

    currentBox = clampBox(card.box)

    if isCorrect:
        card.box = min(currentBox + 1, MAX_BOX)
        card.correctCount += 1
    else:
        card.box = MIN_BOX
        card.wrongCount += 1

    nextDate = today + timedelta(days=INTERVAL_DAYS[card.box])
    card.nextReview = nextDate.isoformat()


def isDue(card: Card, today: date) -> bool:

    """
    Return True if the card should be reviewed today.
    A card with an unreadable date is treated as due.
    """

    try:
        reviewDate = date.fromisoformat(card.nextReview)
    except (TypeError, ValueError):
        return True

    return reviewDate <= today


def describeNextReview(card: Card, today: date) -> str:

    """
    Describe when the card comes back, e.g. "tomorrow" or "in 4 days".
    """

    try:
        reviewDate = date.fromisoformat(card.nextReview)
    except (TypeError, ValueError):
        return "today"

    daysLeft = (reviewDate - today).days

    if daysLeft <= 0:
        return "today"

    if daysLeft == 1:
        return "tomorrow"

    return f"in {daysLeft} days"
