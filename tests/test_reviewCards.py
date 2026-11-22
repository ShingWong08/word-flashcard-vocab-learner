from datetime import date

import pytest

from word_flashcard_vocab_learner import genAITutor, reviewCards, speechHelper
from word_flashcard_vocab_learner.flashCard import Card

TODAY = date(2026, 11, 18)


def makeCard(word="cat", box=1):
    return Card(
        word,
        [f"a {word} is an animal"],
        [[f"My {word}s are asleep."]],
        "",
        box=box,
        nextReview="2026-11-18",
    )


# ---------- Answer checking ----------


def testMaskWordHidesWordAndItsForms():
    assert reviewCards.maskWord("I have two cats.", "cat") == "I have two ____."
    assert reviewCards.maskWord("Cat food", "cat") == "____ food"
    assert reviewCards.maskWord("Concatenate", "cat") == "Concatenate"


def testMakeHint():
    assert reviewCards.makeHint("ambiguous") == "a________ (9 letters)"
    assert reviewCards.makeHint("ice cream") == "i__ _____ (8 letters)"


def testIsSpellingCorrect():
    assert reviewCards.isSpellingCorrect("  Ambiguous. ", "ambiguous") is True
    assert reviewCards.isSpellingCorrect("ice   cream", "ice cream") is True
    assert reviewCards.isSpellingCorrect("ambigous", "ambiguous") is False
    assert reviewCards.isSpellingCorrect("", "ambiguous") is False


def testIsSpokenCorrect():
    assert reviewCards.isSpokenCorrect("(laughs) It's ambiguous.", "ambiguous") is True
    assert reviewCards.isSpokenCorrect("Well known.", "well-known") is True
    assert reviewCards.isSpokenCorrect("Ambitious.", "ambiguous") is False
    assert reviewCards.isSpokenCorrect("", "ambiguous") is False


def testCluesDoNotShowTheWord():
    clues = reviewCards.formatClues(makeCard("cat"))

    assert "cat" not in clues.lower()
    assert "c__ (3 letters)" in clues


# ---------- Sessions ----------


def testSpellingSessionUpdatesScheduleAndRetriesWrongCards(typeAnswers):
    cat = makeCard("cat")
    dog = makeCard("dog", box=3)
    saves = []
    prompts = typeAnswers(["cat", "dgo", "dog"])

    summary = reviewCards.reviewCards(
        [cat, dog],
        reviewCards.MODE_SPELLING,
        saveProgress=lambda: saves.append(1),
        today=TODAY,
        shuffle=False,
    )

    assert summary == {"reviewed": 2, "correct": 1, "wrong": 1, "stopped": False}
    assert len(prompts) == 3
    assert (cat.box, cat.nextReview, cat.correctCount) == (2, "2026-11-20", 1)
    # The retry was right, but only the first answer counts.
    assert (dog.box, dog.nextReview, dog.correctCount, dog.wrongCount) == (
        1,
        "2026-11-19",
        0,
        1,
    )
    assert len(saves) == 2


def testQuittingStopsWithoutChanges(typeAnswers):
    card = makeCard()
    saves = []
    typeAnswers(["q"])

    summary = reviewCards.reviewCards(
        [card],
        reviewCards.MODE_SPELLING,
        saveProgress=lambda: saves.append(1),
        today=TODAY,
    )

    assert summary["stopped"] is True
    assert summary["reviewed"] == 0
    assert card.box == 1
    assert saves == []


def testPracticeDoesNotChangeSchedule(typeAnswers):
    card = makeCard(box=3)
    typeAnswers(["cat"])

    summary = reviewCards.reviewCards(
        [card], reviewCards.MODE_SPELLING, today=TODAY, updateSchedule=False
    )

    assert summary["correct"] == 1
    assert card.box == 3
    assert card.correctCount == 0


def testMaxCardsLimitsSession(typeAnswers):
    cards = [makeCard("cat"), makeCard("dog"), makeCard("pig")]
    typeAnswers(["cat"])

    summary = reviewCards.reviewCards(
        cards, reviewCards.MODE_SPELLING, today=TODAY, shuffle=False, maxCards=1
    )

    assert summary["reviewed"] == 1


def testMeaningModeIsSelfGraded(typeAnswers, capsys):
    card = makeCard()
    typeAnswers(["", "maybe", "y"])

    summary = reviewCards.reviewCards([card], reviewCards.MODE_MEANING, today=TODAY)

    out = capsys.readouterr().out
    assert 'Definitions of "cat":' in out
    assert "Please answer y or n." in out
    assert summary["correct"] == 1


def testListeningModePlaysAndReplays(typeAnswers, monkeypatch):
    played = []
    monkeypatch.setattr(speechHelper, "pronounce", lambda word: played.append(word))
    typeAnswers(["r", "cat"])

    summary = reviewCards.reviewCards(
        [makeCard()], reviewCards.MODE_LISTENING, today=TODAY
    )

    assert played == ["cat", "cat"]
    assert summary["correct"] == 1


def testListeningModeStopsWhenAudioFails(typeAnswers, monkeypatch, capsys):
    def failToPlay(word):
        raise ValueError("ffplay not found")

    monkeypatch.setattr(speechHelper, "pronounce", failToPlay)
    typeAnswers([])

    summary = reviewCards.reviewCards(
        [makeCard()], reviewCards.MODE_LISTENING, today=TODAY
    )

    assert summary["stopped"] is True
    assert "ffplay not found" in capsys.readouterr().out


def testSpeakingModeChecksTranscription(monkeypatch, capsys):
    monkeypatch.setattr(speechHelper, "listenForWord", lambda: "(noise) Cat.")

    summary = reviewCards.reviewCards(
        [makeCard()], reviewCards.MODE_SPEAKING, today=TODAY
    )

    assert "You said: (noise) Cat." in capsys.readouterr().out
    assert summary["correct"] == 1


def testSpeakingModeStopsWhenRecordingFails(monkeypatch):
    def failToRecord():
        raise OSError("no microphone")

    monkeypatch.setattr(speechHelper, "listenForWord", failToRecord)

    summary = reviewCards.reviewCards(
        [makeCard()], reviewCards.MODE_SPEAKING, today=TODAY
    )

    assert summary["stopped"] is True


def testSentenceModeUsesAiVerdict(typeAnswers, monkeypatch, capsys):
    checked = []

    def fakeCheck(word, definition, sentence):
        checked.append(sentence)
        return True, "Nice sentence!"

    monkeypatch.setattr(genAITutor, "checkSentence", fakeCheck)
    typeAnswers(["", "My cat sleeps all day."])

    summary = reviewCards.reviewCards(
        [makeCard()], reviewCards.MODE_SENTENCE, today=TODAY
    )

    assert checked == ["My cat sleeps all day."]
    assert "Feedback: Nice sentence!" in capsys.readouterr().out
    assert summary["correct"] == 1


def testSentenceModeAsksUserWhenVerdictIsUnclear(typeAnswers, monkeypatch):
    monkeypatch.setattr(
        genAITutor, "checkSentence", lambda word, definition, sentence: (None, "Hmm.")
    )
    typeAnswers(["My cat sleeps.", "n", "My cat sleeps a lot.", "y"])

    summary = reviewCards.reviewCards(
        [makeCard()], reviewCards.MODE_SENTENCE, today=TODAY
    )

    assert summary == {"reviewed": 1, "correct": 0, "wrong": 1, "stopped": False}


def testUnknownModeRaises():
    with pytest.raises(ValueError):
        reviewCards.reviewCards([makeCard()], "dancing")


def testAvailableModes(monkeypatch, request):
    assert reviewCards.availableModes() == [
        reviewCards.MODE_MEANING,
        reviewCards.MODE_SPELLING,
    ]

    request.getfixturevalue("enableAI")
    monkeypatch.setattr(speechHelper, "isSpeechAvailable", lambda: True)

    assert reviewCards.availableModes() == [
        reviewCards.MODE_MEANING,
        reviewCards.MODE_SPELLING,
        reviewCards.MODE_LISTENING,
        reviewCards.MODE_SPEAKING,
        reviewCards.MODE_SENTENCE,
    ]


def testMaskWordDoesNotHideTheStartOfALongerWord():
    assert (
        reviewCards.maskWord("The category is broad.", "cat")
        == "The category is broad."
    )
    assert (
        reviewCards.maskWord("Two categories, one cat.", "cat")
        == "Two categories, one ____."
    )
    assert reviewCards.maskWord("I have two cats.", "cat") == "I have two ____."
    assert (
        reviewCards.maskWord("She was cataloguing the cats.", "cat")
        == "She was cataloguing the ____."
    )


def testNormalizeAnswerIgnoresCurlyQuotesAndHyphens():
    assert reviewCards.normalizeAnswer("Don’t") == reviewCards.normalizeAnswer("don't")
    assert reviewCards.normalizeAnswer("ice-cream") == reviewCards.normalizeAnswer(
        "ice cream"
    )
    assert reviewCards.isSpellingCorrect("Don’t", "don't")
    assert reviewCards.isSpellingCorrect("Ice-Cream", "ice cream")


def testCardBackSaysWhenNoMeaningWasSaved():
    card = makeCard("cat")
    card.definitions = []

    text = reviewCards.formatCardBack(card)

    assert "No meaning saved" in text
    assert "No definition found" not in text
