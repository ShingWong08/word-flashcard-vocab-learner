from datetime import date

from word_flashcard_vocab_learner import showProgress
from word_flashcard_vocab_learner.flashCard import Card


TODAY = date(2026, 11, 18)


def makeCard(word, box=1, nextReview="2026-11-18", correct=0, wrong=0):
    return Card(word, ["x"], box=box, nextReview=nextReview, correctCount=correct, wrongCount=wrong)


CARDS = [
    makeCard("cat", box=1, nextReview="2026-11-10", correct=1, wrong=3),
    makeCard("dog", box=2, nextReview="2026-11-20", correct=2, wrong=1),
    makeCard("pig", box=5, nextReview="2026-12-30", correct=6, wrong=0),
    makeCard("cow", box=1, nextReview="2026-11-18"),
]


def test_calculate_stats():
    stats = showProgress.calculateStats(CARDS, TODAY)

    assert stats["words"] == 4
    assert stats["dueToday"] == 2
    assert stats["dueThisWeek"] == 3
    assert stats["mastered"] == 1
    assert stats["neverReviewed"] == 1
    assert (stats["correct"], stats["reviewed"]) == (9, 13)
    assert stats["boxes"] == {1: 2, 2: 1, 3: 0, 4: 0, 5: 1}


def test_format_bar():
    assert showProgress.formatBar(0, 10) == ""
    assert showProgress.formatBar(10, 10) == "█" * showProgress.MAX_BAR_LENGTH
    assert showProgress.formatBar(1, 1000) == "█"


def test_hardest_words():
    assert [eachCard.word for eachCard in showProgress.hardestWords(CARDS)] == ["cat", "dog"]


def test_show_progress(capsys):
    showProgress.showProgress(CARDS, TODAY)

    out = capsys.readouterr().out
    assert "Your progress" in out
    assert "Accuracy          9 of 13 answers correct (69%)" in out
    assert "Box 5  (every 14 days)  1" in out
    assert "Words to practise more" in out


def test_show_progress_with_empty_deck(capsys):
    showProgress.showProgress([], TODAY)
    assert "Your deck is empty" in capsys.readouterr().out
