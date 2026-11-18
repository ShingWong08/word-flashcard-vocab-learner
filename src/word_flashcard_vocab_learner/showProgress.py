from datetime import date, timedelta

from word_flashcard_vocab_learner import leitnerScheduler, terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card


BAR_CHARACTER = "█"
MAX_BAR_LENGTH = 30
WEEK_DAYS = 7


def countDueWithin(cards: list[Card], today: date, days: int) -> int:

    """
    Count the cards that are due within the next number of days (0 = today, including overdue cards).
    """

    lastDay = today + timedelta(days=days)
    count = 0

    for eachCard in cards:
        if leitnerScheduler.isDue(eachCard, lastDay):
            count += 1

    return count


def countByBox(cards: list[Card]) -> dict[int, int]:

    """
    Return how many cards are in each Leitner box, e.g. {1: 4, 2: 1, 3: 0, 4: 0, 5: 2}.
    """

    counts = {}
    for eachBox in range(leitnerScheduler.MIN_BOX, leitnerScheduler.MAX_BOX + 1):
        counts[eachBox] = 0

    for eachCard in cards:
        counts[leitnerScheduler.clampBox(eachCard.box)] += 1

    return counts


def calculateStats(cards: list[Card], today: date) -> dict:

    """
    Collect the numbers shown on the progress screen.
    """

    correct = 0
    reviewed = 0
    for eachCard in cards:
        correct += eachCard.correctCount
        reviewed += eachCard.timesReviewed()

    boxes = countByBox(cards)

    return {
        "words": len(cards),
        "dueToday": countDueWithin(cards, today, 0),
        "dueThisWeek": countDueWithin(cards, today, WEEK_DAYS - 1),
        "mastered": boxes[leitnerScheduler.MAX_BOX],
        "neverReviewed": sum(1 for eachCard in cards if eachCard.timesReviewed() == 0),
        "correct": correct,
        "reviewed": reviewed,
        "boxes": boxes,
    }


def formatBar(count: int, largestCount: int) -> str:

    """
    A bar whose length shows count compared with the largest count (at least 1 block when count > 0).
    """

    if count == 0 or largestCount == 0:
        return ""

    length = max(1, round(count * MAX_BAR_LENGTH / largestCount))
    return BAR_CHARACTER * length


def hardestWords(cards: list[Card], limit: int = 5) -> list[Card]:

    """
    The cards answered wrongly most often (only cards with at least one wrong answer).
    """

    wrongCards = [eachCard for eachCard in cards if eachCard.wrongCount > 0]
    wrongCards.sort(key=lambda eachCard: (-eachCard.wrongCount, eachCard.correctCount, eachCard.word.casefold()))

    return wrongCards[:limit]


def showProgress(cards: list[Card], today: date | None = None) -> None:

    """
    Print the progress screen: totals, accuracy, cards per box and the hardest words.
    """

    if today is None:
        today = date.today()

    if len(cards) == 0:
        print(ChatColor.paint("Your deck is empty. Look up some words and add them first.", ChatColor.ORANGE))
        return

    stats = calculateStats(cards, today)

    terminalDisplay.printHeading("Your progress")

    if stats["reviewed"] > 0:
        percent = round(stats["correct"] * 100 / stats["reviewed"])
        accuracy = f"{stats['correct']} of {stats['reviewed']} answers correct ({percent}%)"
    else:
        accuracy = "no reviews yet"

    labelWidth = 16
    print(terminalDisplay.labelLine("Words in deck", stats["words"], labelWidth))
    print(terminalDisplay.labelLine("Due today", stats["dueToday"], labelWidth))
    print(terminalDisplay.labelLine("Due this week", stats["dueThisWeek"], labelWidth))
    print(terminalDisplay.labelLine("Mastered (box 5)", stats["mastered"], labelWidth))
    print(terminalDisplay.labelLine("Never reviewed", stats["neverReviewed"], labelWidth))
    print(terminalDisplay.labelLine("Accuracy", accuracy, labelWidth))

    print()
    print(ChatColor.paint("  Cards per box", ChatColor.BOLD))
    print()

    largestCount = max(stats["boxes"].values())
    countWidth = len(str(largestCount))

    waitTexts = {}
    for eachBox in stats["boxes"]:
        waitTexts[eachBox] = f"(every {terminalDisplay.plural(leitnerScheduler.INTERVAL_DAYS[eachBox], 'day')})"
    waitWidth = max(len(eachText) for eachText in waitTexts.values())

    for eachBox, eachCount in stats["boxes"].items():
        label = ChatColor.paint(f"    Box {eachBox}", ChatColor.DARK_GRAY)
        wait = ChatColor.paint(f"{waitTexts[eachBox]:<{waitWidth}}", ChatColor.DARK_GRAY)
        bar = ChatColor.paint(formatBar(eachCount, largestCount), ChatColor.CYAN)
        print(f"{label}  {wait}  {eachCount:>{countWidth}}  {bar}")

    hardCards = hardestWords(cards)

    if len(hardCards) > 0:
        print()
        print(ChatColor.paint("  Words to practise more", ChatColor.BOLD))
        print()

        wordWidth = max(len(eachCard.word) for eachCard in hardCards)
        for eachCard in hardCards:
            score = ChatColor.paint(f"wrong {eachCard.wrongCount}, right {eachCard.correctCount}", ChatColor.DARK_GRAY)
            print(f"    {eachCard.word:<{wordWidth}}  {score}")
