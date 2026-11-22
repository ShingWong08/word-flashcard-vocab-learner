from datetime import date, timedelta

from word_flashcard_vocab_learner import leitnerScheduler, terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card

BAR_CHARACTER = "█"
MAX_BAR_LENGTH = 30
WEEK_DAYS = 7


def countDueWithin(cards: list[Card], today: date, days: int) -> int:
    """
    Count the cards that are due within the next number of days (0 = today, including
    overdue cards).
    """

    lastDay = today + timedelta(days=days)
    return sum(leitnerScheduler.isDue(eachCard, lastDay) for eachCard in cards)


def countByBox(cards: list[Card]) -> dict[int, int]:
    """
    Return how many cards are in each Leitner box, e.g. {1: 4, 2: 1, 3: 0, 4: 0, 5: 2}.
    """

    counts = dict.fromkeys(
        range(leitnerScheduler.MIN_BOX, leitnerScheduler.MAX_BOX + 1), 0
    )

    for eachCard in cards:
        counts[leitnerScheduler.clampBox(eachCard.box)] += 1

    return counts


def calculateStats(cards: list[Card], today: date) -> dict:
    """
    Collect the numbers shown on the progress screen.
    """

    boxes = countByBox(cards)
    timesReviewed = [eachCard.timesReviewed() for eachCard in cards]

    return {
        "words": len(cards),
        "dueToday": countDueWithin(cards, today, 0),
        "dueThisWeek": countDueWithin(cards, today, WEEK_DAYS - 1),
        "mastered": boxes[leitnerScheduler.MAX_BOX],
        "neverReviewed": timesReviewed.count(0),
        "correct": sum(eachCard.correctCount for eachCard in cards),
        "reviewed": sum(timesReviewed),
        "boxes": boxes,
    }


def formatBar(count: int, largestCount: int) -> str:
    """
    A bar whose length shows count compared with the largest count (at least 1 block
    when count > 0).
    """

    if count == 0 or largestCount == 0:
        return ""

    return BAR_CHARACTER * max(1, round(count * MAX_BAR_LENGTH / largestCount))


def hardestWords(cards: list[Card], limit: int = 5) -> list[Card]:
    """
    The cards answered wrongly most often (only cards with at least one wrong answer).
    """

    wrongCards = [eachCard for eachCard in cards if eachCard.wrongCount > 0]
    wrongCards.sort(
        key=lambda eachCard: (
            -eachCard.wrongCount,
            eachCard.correctCount,
            eachCard.word.casefold(),
        )
    )

    return wrongCards[:limit]


def showProgress(cards: list[Card], today: date | None = None) -> None:
    """
    Print the progress screen: totals, accuracy, cards per box and the hardest words.
    """

    if today is None:
        today = date.today()

    if not cards:
        print(
            ChatColor.paint(
                "Your deck is empty. Look up some words and add them first.",
                ChatColor.ORANGE,
            )
        )
        return

    stats = calculateStats(cards, today)

    terminalDisplay.printHeading("Your progress")

    if stats["reviewed"] > 0:
        percent = round(stats["correct"] * 100 / stats["reviewed"])
        accuracy = (
            f"{stats['correct']} of {stats['reviewed']} answers correct ({percent}%)"
        )
    else:
        accuracy = "no reviews yet"

    for label, value in [
        ("Words in deck", stats["words"]),
        ("Due today", stats["dueToday"]),
        ("Due this week", stats["dueThisWeek"]),
        ("Mastered (box 5)", stats["mastered"]),
        ("Never reviewed", stats["neverReviewed"]),
        ("Accuracy", accuracy),
    ]:
        print(terminalDisplay.labelLine(label, value, 16))

    print()
    print(ChatColor.paint("  Cards per box", ChatColor.BOLD))
    print()

    largestCount = max(stats["boxes"].values())
    countWidth = len(str(largestCount))

    intervals = leitnerScheduler.INTERVAL_DAYS
    waitTexts = {
        eachBox: f"(every {terminalDisplay.plural(intervals[eachBox], 'day')})"
        for eachBox in stats["boxes"]
    }
    waitWidth = max(map(len, waitTexts.values()))

    for eachBox, eachCount in stats["boxes"].items():
        label = ChatColor.paint(f"    Box {eachBox}", ChatColor.DARK_GRAY)
        wait = ChatColor.paint(
            f"{waitTexts[eachBox]:<{waitWidth}}", ChatColor.DARK_GRAY
        )
        bar = ChatColor.paint(formatBar(eachCount, largestCount), ChatColor.CYAN)
        print(f"{label}  {wait}  {eachCount:>{countWidth}}  {bar}")

    hardCards = hardestWords(cards)

    if hardCards:
        print()
        print(ChatColor.paint("  Words to practise more", ChatColor.BOLD))
        print()

        wordWidth = max(len(eachCard.word) for eachCard in hardCards)
        for eachCard in hardCards:
            score = ChatColor.paint(
                f"wrong {eachCard.wrongCount}, right {eachCard.correctCount}",
                ChatColor.DARK_GRAY,
            )
            print(f"    {eachCard.word:<{wordWidth}}  {score}")
