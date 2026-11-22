from datetime import date

import requests

import word_flashcard_vocab_learner as app
from word_flashcard_vocab_learner import cardDeck, genAITutor
from word_flashcard_vocab_learner import connectFreeDictionaryAPI as dictionary
from word_flashcard_vocab_learner.flashCard import Card

CAT_LOOKUP = {
    "word": "cat",
    "definitions": ["a pet"],
    "examples": [["My cat is asleep."]],
}


def fakeLookup(monkeypatch):
    monkeypatch.setattr(dictionary, "getWordDefinition", lambda word: CAT_LOOKUP)


def deckPath(tmp_path):
    return str(tmp_path / "deck.json")


def saveCat(tmp_path, nextReview=None):
    if nextReview is None:
        nextReview = date.today().isoformat()

    card = Card("cat", ["a pet"], [["My cat is asleep."]], "貓", nextReview=nextReview)
    cardDeck.saveDeck([card], deckPath(tmp_path))


def testLookUpWordAndAddItToDeck(monkeypatch, capsys, tmp_path, typeAnswers):
    fakeLookup(monkeypatch)
    typeAnswers(["1", "cat", "y", "", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert 'Definitions of "cat":' in out
    assert "  1. a pet" in out
    assert "     > My cat is asleep." in out
    assert "Chinese" not in out
    assert 'Added "cat" to your deck (1 word).' in out
    assert "Goodbye!" in out

    savedCards = cardDeck.loadDeck(deckPath(tmp_path))
    assert [eachCard.word for eachCard in savedCards] == ["cat"]


def testTranslationIsShownAndSavedWhenAiIsSetUp(
    monkeypatch, capsys, tmp_path, typeAnswers
):
    fakeLookup(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setattr(genAITutor, "translateWord", lambda word, definition: "貓")
    typeAnswers(["1", "cat", "y", "", "q"])

    app.main(deckPath(tmp_path))

    assert "Chinese: 貓" in capsys.readouterr().out
    assert cardDeck.loadDeck(deckPath(tmp_path))[0].translation == "貓"


def testWordAlreadyInDeckIsNotOfferedAgain(monkeypatch, capsys, tmp_path, typeAnswers):
    fakeLookup(monkeypatch)
    saveCat(tmp_path)
    typeAnswers(["1", "cat", "", "q"])

    app.main(deckPath(tmp_path))

    assert '"cat" is already in your deck (box 1).' in capsys.readouterr().out


def testMainSurvivesNetworkError(monkeypatch, capsys, tmp_path, typeAnswers):
    def fail(word):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(dictionary, "getWordDefinition", fail)
    typeAnswers(["1", "cat", "", "quit"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Could not reach the dictionary" in out
    assert "Goodbye!" in out


def testReviewDueCardInSpellingMode(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["2", "2", "cat", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Due today: 1 card." in out
    assert "Card 1 of 1" in out
    assert "Correct!" in out
    assert "Session finished" in out
    assert "  Reviewed  1 card" in out
    assert "  Score     100%" in out

    savedCard = cardDeck.loadDeck(deckPath(tmp_path))[0]
    assert savedCard.box == 2
    assert savedCard.correctCount == 1


def testNoDueCardsOffersPractice(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path, nextReview="2999-01-01")
    typeAnswers(["2", "n", "q"])

    app.main(deckPath(tmp_path))

    assert "No cards are due today. Next review: 2999-01-01." in capsys.readouterr().out


def testReviewEmptyDeck(capsys, tmp_path, typeAnswers):
    typeAnswers(["2", "q"])

    app.main(deckPath(tmp_path))

    assert "Your deck is empty" in capsys.readouterr().out


def testViewDeck(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["4", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Your deck: 1 word, 1 due today" in out
    assert "cat" in out
    assert "貓" in out


LONG_TRANSLATION = (
    "這是一個非常長的中文翻譯，用來測試表格會不會超出畫面寬度，看起來會折行"
)


def testViewDeckShortensALongTranslationToFitTheTable(
    capsys, tmp_path, typeAnswers, monkeypatch
):
    monkeypatch.setenv("COLUMNS", "80")
    longWord = "pneumonoultramicroscopicsilicovolcanoconiosis"
    cards = [
        Card(longWord, ["a lung disease"], [[]], LONG_TRANSLATION),
        Card("cat", ["a pet"], [[]], LONG_TRANSLATION),
    ]
    cardDeck.saveDeck(cards, deckPath(tmp_path))
    typeAnswers(["4", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    tableLines = out.split("Your deck:")[1].split("Saved in:")[0].splitlines()
    assert (
        max(len(eachLine) for eachLine in tableLines) <= 80
    )  # no row wraps past the edge
    assert "…" in out  # the translation is shortened, not dropped
    assert "這是一個非常長的中文翻譯" in out


def testViewDeckShortensALongTranslationInANarrowTerminal(
    capsys, tmp_path, typeAnswers, monkeypatch
):
    monkeypatch.setenv("COLUMNS", "40")
    cardDeck.saveDeck(
        [Card("cat", ["a pet"], [[]], LONG_TRANSLATION)], deckPath(tmp_path)
    )
    typeAnswers(["4", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    translationLines = [
        eachLine
        for eachLine in out.splitlines()
        if eachLine.strip().startswith("這是一個")
    ]
    assert len(translationLines) == 1
    assert len(translationLines[0]) <= 40
    assert translationLines[0].strip().endswith("…")


def testRemoveWord(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["7", "CAT", "y", "", "q"])

    app.main(deckPath(tmp_path))

    assert "Removed 1 word." in capsys.readouterr().out
    assert cardDeck.loadDeck(deckPath(tmp_path)) == []


def testDamagedDeckIsNotOverwritten(capsys, tmp_path, typeAnswers):
    path = tmp_path / "deck.json"
    path.write_text("{broken", encoding="utf-8")
    typeAnswers([])

    app.main(str(path))

    assert "damaged" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == "{broken"


def testUnknownMenuChoice(capsys, tmp_path, typeAnswers):
    typeAnswers(["x", "q"])

    app.main(deckPath(tmp_path))

    assert "Please choose 1 - 9, c or q." in capsys.readouterr().out


def testMainUsesDefaultDeckPath(capsys, tmp_path, typeAnswers):
    typeAnswers(["q"])

    app.main()

    assert "Your deck has 0 words" in capsys.readouterr().out


def testMenuShowsDueCount(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["q"])

    app.main(deckPath(tmp_path))

    assert "2. Review cards  (1 due)" in capsys.readouterr().out


def testClearScreenCommand(monkeypatch, tmp_path, typeAnswers):
    cleared = []
    monkeypatch.setattr(app.terminalDisplay, "clearScreen", lambda: cleared.append(1))
    typeAnswers(["clear", "c", "q"])

    app.main(deckPath(tmp_path))

    assert len(cleared) == 2


def testImportWordsFromTextFile(monkeypatch, capsys, tmp_path, typeAnswers):
    wordList = tmp_path / "words.txt"
    wordList.write_text(
        "1. ambiguous - unclear\n2. cat - 貓\n3. qwzx\n", encoding="utf-8"
    )

    def fakeGetWordDefinition(word):
        if word == "qwzx":
            return {"word": word, "definitions": [], "examples": []}
        return {"word": word, "definitions": [f"meaning of {word}"], "examples": [[]]}

    monkeypatch.setattr(dictionary, "getWordDefinition", fakeGetWordDefinition)
    typeAnswers(["3", f'"{wordList}"', "", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Words found in words.txt" in out
    assert "1. ambiguous" in out
    assert "skipped: not found in the dictionary" in out
    assert "Added 2, skipped 1." in out
    assert [eachCard.word for eachCard in cardDeck.loadDeck(deckPath(tmp_path))] == [
        "ambiguous",
        "cat",
    ]


def testProgressScreen(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["5", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Your progress" in out
    assert "Words in deck     1" in out


def testExportDeck(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    exportPath = tmp_path / "my words"
    typeAnswers(["6", str(exportPath), "q"])

    app.main(deckPath(tmp_path))

    assert "Exported 1 word to" in capsys.readouterr().out
    assert "貓" in (tmp_path / "my words.csv").read_text(encoding="utf-8-sig")


def testExportAsksBeforeReplacing(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    existing = tmp_path / "old.csv"
    existing.write_text("keep me", encoding="utf-8")
    typeAnswers(["6", str(existing), "n", "q"])

    app.main(deckPath(tmp_path))

    assert existing.read_text(encoding="utf-8") == "keep me"


def testEditCardChangesWordTranslationAndMeaning(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["8", "cat", "", "貓咪", "a small pet", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert 'Updated "cat".' in out

    savedCard = cardDeck.loadDeck(deckPath(tmp_path))[0]
    assert savedCard.translation == "貓咪"
    assert savedCard.definitions == ["a small pet"]


def testEditCardKeepsValuesWhenEnterIsPressed(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path)
    typeAnswers(["8", "cat", "", "", "", "q"])

    app.main(deckPath(tmp_path))

    savedCard = cardDeck.loadDeck(deckPath(tmp_path))[0]
    assert savedCard.translation == "貓"
    assert savedCard.definitions == ["a pet"]


def testEditCardRefusesAWordThatIsAlreadyInTheDeck(capsys, tmp_path, typeAnswers):
    cardDeck.saveDeck(
        [Card("cat", ["a pet"], [[]]), Card("dog", ["a pet"], [[]])], deckPath(tmp_path)
    )
    typeAnswers(["8", "cat", "dog", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert '"dog" is already in your deck' in out
    assert [eachCard.word for eachCard in cardDeck.loadDeck(deckPath(tmp_path))] == [
        "cat",
        "dog",
    ]


def testPractiseOneWord(capsys, tmp_path, typeAnswers):
    saveCat(tmp_path, nextReview="2999-01-01")
    typeAnswers(["9", "cat", "1", "", "y", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Card 1 of 1" in out
    assert "Session finished" in out

    savedCard = cardDeck.loadDeck(deckPath(tmp_path))[0]
    assert savedCard.correctCount == 1


def testViewALongDeckOnePageAtATime(capsys, tmp_path, typeAnswers):
    words = ["word" + str(index) for index in range(1, 36)]
    cardDeck.saveDeck(
        [Card(eachWord, ["a meaning"], [[]]) for eachWord in words], deckPath(tmp_path)
    )
    prompts = typeAnswers(["4", "", "", "q"])

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "30 words per page" in out
    assert (
        prompts.count("Enter = next page, q = back: ") == 1
    )  # 35 words = 2 pages, one prompt between them
    assert out.count("Box  Next review") == 2  # a header on every page
    assert "  Saved in:" in out


def testReviewOffersToCarryOnAfterTwentyCards(capsys, tmp_path, typeAnswers):
    words = ["word" + str(index) for index in range(1, 22)]
    cardDeck.saveDeck(
        [Card(eachWord, ["a meaning"], [[]]) for eachWord in words], deckPath(tmp_path)
    )

    answers = ["2", "1"]
    for _ in range(20):
        answers.extend(["", "y"])
    answers.extend(["y", "", "y", "q"])
    prompts = typeAnswers(answers)

    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "Continue with the next 1 card? (y/N) " in prompts
    assert out.count("Session finished") == 2
    assert (
        sum(eachCard.correctCount for eachCard in cardDeck.loadDeck(deckPath(tmp_path)))
        == 21
    )


def testReviewKeepsGoingWhenTheDeckCannotBeSaved(
    capsys, tmp_path, typeAnswers, makeDeckFolderReadOnly
):
    saveCat(tmp_path)
    makeDeckFolderReadOnly()

    typeAnswers(["2", "2", "cat", "q"])
    app.main(deckPath(tmp_path))

    out = capsys.readouterr().out
    assert "cannot be written" in out
    assert "Your answers are kept for this session" in out
    assert "Correct!" in out
    assert "Goodbye!" in out
