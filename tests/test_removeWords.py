import pytest

from word_flashcard_vocab_learner import cardDeck, removeWords
from word_flashcard_vocab_learner.flashCard import Card


def makeDeck():
    return [
        Card("banana", ["a fruit"], box=1),
        Card("ambiguous", ["unclear"], box=5, correctCount=4),
        Card("accept", ["take"], box=2),
        Card("ice cream", ["a dessert"], box=1),
        Card("ambition", ["a strong wish"], box=5),
    ]


def numbered(cards):
    # 1. accept  2. ambiguous  3. ambition  4. banana  5. ice cream
    return cardDeck.sortByWord(cards)


def words(cards):
    return [eachCard.word for eachCard in cards]


# ---------- Choosing cards ----------


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("banana", ["banana"]),
        ("BANANA, accept", ["accept", "banana"]),
        ("2", ["ambiguous"]),
        ("1,3", ["accept", "ambition"]),
        ("1 3", ["accept", "ambition"]),
        ("2-4", ["ambiguous", "ambition", "banana"]),
        ("4 - 2", ["ambiguous", "ambition", "banana"]),
        ("5, banana, 1-2", ["accept", "ambiguous", "banana", "ice cream"]),
        ("ice cream", ["ice cream"]),
        ("banana accept", ["accept", "banana"]),
        ("amb*", ["ambiguous", "ambition"]),
        ("*a", ["banana"]),
        ("box 5", ["ambiguous", "ambition"]),
        ("box1", ["banana", "ice cream"]),
        ("mastered", ["ambiguous", "ambition"]),
        ("all", ["accept", "ambiguous", "ambition", "banana", "ice cream"]),
        ("1, 1, accept", ["accept"]),
    ],
)
def testSelectCards(answer, expected):
    selected, problems = removeWords.selectCards(answer, numbered(makeDeck()))

    assert problems == []
    assert words(selected) == expected


@pytest.mark.parametrize(
    "answer, problem",
    [
        ("6", "There is no number 6. Choose from 1 to 5."),
        ("0-2", "There is no number 0-2. Choose from 1 to 5."),
        ("apple", '"apple" is not in your deck.'),
        ("zz*", 'No words match "zz*".'),
        ("box 9", "There is no box 9. Boxes go from 1 to 5."),
        ("box 3", "There are no cards in box 3."),
    ],
)
def testSelectCardsReportsProblems(answer, problem):
    selected, problems = removeWords.selectCards(answer, numbered(makeDeck()))

    assert selected == []
    assert problems == [problem]


def testSelectCardsReportsEveryProblemButKeepsValidParts():
    selected, problems = removeWords.selectCards(
        "banana, apple, 9", numbered(makeDeck())
    )

    assert words(selected) == ["banana"]
    assert len(problems) == 2


# ---------- Removing and undoing ----------


def testRemoveAndUndoKeepProgress(tmp_path):
    path = str(tmp_path / "deck.json")
    cards = makeDeck()
    cardDeck.saveDeck(cards, path)
    ambiguous = cards[1]

    removeWords.removeCards(cards, [ambiguous], path)

    assert "ambiguous" not in words(cardDeck.loadDeck(path))
    assert "ambiguous" in words(cardDeck.loadDeck(cardDeck.backupPath(path)))

    restored = removeWords.undoRemoval(cards, [ambiguous], path)

    assert words(restored) == ["ambiguous"]
    savedCard = cardDeck.findCard(cardDeck.loadDeck(path), "ambiguous")
    assert (savedCard.box, savedCard.correctCount) == (5, 4)


def testUndoSkipsWordsAddedAgain(tmp_path):
    path = str(tmp_path / "deck.json")
    cards = [Card("cat", ["a new card"])]

    restored = removeWords.undoRemoval(cards, [Card("Cat", ["the old card"])], path)

    assert restored == []
    assert cards[0].definitions == ["a new card"]


# ---------- The whole screen ----------


def runScreen(tmp_path, typeAnswers, answers, cards=None):
    path = str(tmp_path / "deck.json")
    if cards is None:
        cards = makeDeck()
    cardDeck.saveDeck(cards, path)

    typeAnswers(answers)
    removeWords.removeWords(cards, path)

    return cards, path


def testScreenListsNumberedWordsAndBoxCounts(tmp_path, typeAnswers, capsys):
    runScreen(tmp_path, typeAnswers, [""])

    out = capsys.readouterr().out
    assert "1. accept" in out
    assert "5. ice cream" in out
    assert "5 words  ·  box 1: 2,  box 2: 1,  box 5: 2" in out
    assert "What to remove:" in out


def testScreenRemovesByNumberAfterConfirmation(tmp_path, typeAnswers, capsys):
    cards, path = runScreen(tmp_path, typeAnswers, ["1, 4", "y", ""])

    out = capsys.readouterr().out
    assert "These 2 words will be removed:" in out
    assert "accept, banana" in out
    assert "Removed 2 words." in out
    assert words(cardDeck.loadDeck(path)) == ["ambiguous", "ice cream", "ambition"]


def testScreenShowsNewNumbersAfterRemoval(tmp_path, typeAnswers, capsys):
    runScreen(tmp_path, typeAnswers, ["accept", "y", ""])

    out = capsys.readouterr().out
    assert "This word will be removed:" in out
    assert "Removed 1 word." in out
    assert "The numbers have changed:" in out
    assert "1. ambiguous" in out.split("The numbers have changed:")[1]


def testScreenCancelRemovesNothing(tmp_path, typeAnswers, capsys):
    cards, path = runScreen(tmp_path, typeAnswers, ["banana", "n", ""])

    assert "Nothing was removed." in capsys.readouterr().out
    assert len(cardDeck.loadDeck(path)) == 5


def testScreenWithATypoRemovesNothing(tmp_path, typeAnswers, capsys):
    cards, path = runScreen(tmp_path, typeAnswers, ["banana, bananna", ""])

    out = capsys.readouterr().out
    assert '"bananna" is not in your deck.' in out
    assert "Nothing was removed." in out
    assert len(cards) == 5


def testRemoveAllNeedsTypedConfirmation(tmp_path, typeAnswers, capsys):
    cards, path = runScreen(
        tmp_path, typeAnswers, ["all", "y", "all", "delete all", ""]
    )

    out = capsys.readouterr().out
    assert "Nothing was removed." in out
    assert "Removed 5 words." in out
    assert "Your deck is now empty." in out
    assert cards == []
    assert cardDeck.loadDeck(path) == []
    assert len(cardDeck.loadDeck(cardDeck.backupPath(path))) == 5


def testUndoAfterRemoveAll(tmp_path, typeAnswers, capsys):
    cards, path = runScreen(
        tmp_path, typeAnswers, ["all", "DELETE ALL", "1", "u", "u", ""]
    )

    out = capsys.readouterr().out
    assert "Your deck is empty. Type u to undo" in out
    assert "Put back 5 words:" in out
    assert "Nothing to undo." in out
    assert len(cardDeck.loadDeck(path)) == 5


def testUndoTwiceRestoresBothRemovals(tmp_path, typeAnswers):
    cards, path = runScreen(
        tmp_path, typeAnswers, ["banana", "y", "accept", "y", "u", "u", ""]
    )

    assert sorted(words(cards)) == [
        "accept",
        "ambiguous",
        "ambition",
        "banana",
        "ice cream",
    ]


def testListAndHelpCommands(tmp_path, typeAnswers, capsys):
    runScreen(tmp_path, typeAnswers, ["banana", "y", "l", "h", ""])

    out = capsys.readouterr().out
    assert "4 words  ·" in out
    assert out.count("What to remove:") == 2


def testEmptyDeck(tmp_path, typeAnswers, capsys):
    typeAnswers([])
    removeWords.removeWords([], str(tmp_path / "deck.json"))

    assert "nothing to remove" in capsys.readouterr().out
