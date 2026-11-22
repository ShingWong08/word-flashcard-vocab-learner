from datetime import date, timedelta

from word_flashcard_vocab_learner.flashCard import Card

MIN_BOX = 1
MAX_BOX = 5

# Leitner system: days to wait before the next review, for each box.
# A right answer moves the card up one box, a wrong answer sends it back to box 1.
INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}


def clampBox(box: int) -> int:
    """
    Keep a box number between MIN_BOX and MAX_BOX (in case the deck file was edited by
    hand).

    Parameters:
        Mandatory:
            - box (int): The box number. Anything int() can read is accepted, e.g. 3,
              "3" or 2.7 (which becomes 2).
    Returns:
        int: The box, at least MIN_BOX (1) and at most MAX_BOX (5). A value that is not
        a number at all (e.g. None or "x") becomes MIN_BOX.
    """

    try:
        box = int(box)
    except (TypeError, ValueError):
        box = MIN_BOX

    return max(MIN_BOX, min(box, MAX_BOX))


def recordAnswer(card: Card, isCorrect: bool, today: date) -> None:
    """
    Update a card after it has been reviewed.
    Right answer: move up one box (at most MAX_BOX) and wait longer.
    Wrong answer: go back to box 1 and come back tomorrow.
    The next review date is today plus the waiting time of the new box (INTERVAL_DAYS).

    Parameters:
        Mandatory:
            - card (Card): The card that was reviewed. It is changed in place: its box,
              nextReview and correctCount or wrongCount.
            - isCorrect (bool): True if the answer was right, False if it was wrong.
            - today (date): The day of the review, which the next review date is
              counted from.
    """

    if isCorrect:
        card.box = min(clampBox(card.box) + 1, MAX_BOX)
        card.correctCount += 1
    else:
        card.box = MIN_BOX
        card.wrongCount += 1

    card.nextReview = (today + timedelta(days=INTERVAL_DAYS[card.box])).isoformat()


def isDue(card: Card, today: date) -> bool:
    """
    Tell whether the card should be reviewed on a given day.
    A card with an unreadable date is treated as due.

    Parameters:
        Mandatory:
            - card (Card): The card to check.
            - today (date): The day to check for. A card whose next review date is on
              or before this day is due (overdue cards are due too).
    Returns:
        bool: True if the card is due, otherwise False.
    """

    try:
        reviewDate = date.fromisoformat(card.nextReview)
    except (TypeError, ValueError):
        return True

    return reviewDate <= today


def describeNextReview(card: Card, today: date) -> str:
    """
    Describe when the card comes back, in words for the user.

    Parameters:
        Mandatory:
            - card (Card): The card, usually just after recordAnswer changed it.
            - today (date): The day to count from.
    Returns:
        str: "today" (also for an overdue card or an unreadable date), "tomorrow", or
        "in N days", e.g. "in 4 days".
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
