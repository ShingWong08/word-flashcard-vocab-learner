from datetime import date, timedelta

from word_flashcard_vocab_learner import leitnerScheduler, terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card

BAR_CHARACTER = "█"
MAX_BAR_LENGTH = 30
WEEK_DAYS = 7


def countDueWithin(cards: list[Card], today: date, days: int) -> int:
    """
    Count the cards that are due within the next number of days.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck.
            - today (date): The day to count from.
            - days (int): How many days ahead to look: 0 counts the cards due today, 6
              the cards due within this week (today plus 6 days). Overdue cards are
              always counted.
    Returns:
        int: The number of due cards.
    """

    lastDay = today + timedelta(days=days)
    return sum(leitnerScheduler.isDue(eachCard, lastDay) for eachCard in cards)


def countByBox(cards: list[Card]) -> dict[int, int]:
    """
    Return how many cards are in each Leitner box, e.g. {1: 4, 2: 1, 3: 0, 4: 0, 5: 2}.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. A box outside 1-5 (from a hand-edited deck)
              is counted in the nearest box (see leitnerScheduler.clampBox).
    Returns:
        dict[int, int]: {box: number of cards} for every box from 1 to 5, in order,
        including the empty ones.
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

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck.
            - today (date): The day used for the "due" numbers.
    Returns:
        dict: The numbers:
            - "words": how many cards are in the deck;
            - "dueToday": cards due today, overdue cards included;
            - "dueThisWeek": cards due within the next 7 days, today included;
            - "mastered": cards in box 5;
            - "neverReviewed": cards that have no answers yet;
            - "correct": right answers over all cards;
            - "reviewed": all answers over all cards;
            - "boxes": cards per box (see countByBox).
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
    A bar whose length shows count compared with the largest count, for the "cards per
    box" chart.

    Parameters:
        Mandatory:
            - count (int): The number this bar stands for.
            - largestCount (int): The largest number in the chart. Its bar is
              MAX_BAR_LENGTH blocks long.
    Returns:
        str: The bar, made of BAR_CHARACTER blocks. At least 1 block when count is
        above 0, so a small number is still visible; "" when count or largestCount
        is 0.
    """

    if count == 0 or largestCount == 0:
        return ""

    return BAR_CHARACTER * max(1, round(count * MAX_BAR_LENGTH / largestCount))


def hardestWords(cards: list[Card], limit: int = 5) -> list[Card]:
    """
    The cards answered wrongly most often (only cards with at least one wrong answer).

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck.
        Optional:
            - limit (int): The most cards to return. Default: 5.
    Returns:
        list[Card]: The cards with the most wrong answers first. With the same number
        of wrong answers, the card with fewer right answers comes first, then
        alphabetical order.
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
    An empty deck only gets a short message.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck.
        Optional:
            - today (date | None): The day used for the "due" numbers.
              Default: None (today's date).
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
