import json

import pytest

from word_flashcard_vocab_learner import genAITutor


def noAPICall(*arguments, **keywordArguments):
    raise AssertionError("The API should not be called")


def testTranslateWordCallsAiAndSavesCache(monkeypatch, tmp_path):
    sentMessages = []

    def fakeConnectGenAI(userMessage, **options):
        sentMessages.append(userMessage)
        return "「含糊不清」"

    monkeypatch.setattr(genAITutor, "connectGenAI", fakeConnectGenAI)

    translation = genAITutor.translateWord(
        "Ambiguous", "open to more than one meaning", cacheDir=str(tmp_path)
    )

    assert translation == "含糊不清"
    assert "open to more than one meaning" in sentMessages[0]

    savedCache = json.loads((tmp_path / "zh-TW.json").read_text(encoding="utf-8"))
    assert savedCache == {"ambiguous": "含糊不清"}

    monkeypatch.setattr(genAITutor, "connectGenAI", noAPICall)
    assert genAITutor.translateWord("ambiguous", cacheDir=str(tmp_path)) == "含糊不清"


def testTranslateWordReadsExistingCache(monkeypatch, tmp_path):
    (tmp_path / "zh-TW.json").write_text('{"cat": "貓"}', encoding="utf-8")
    monkeypatch.setattr(genAITutor, "connectGenAI", noAPICall)

    assert genAITutor.translateWord("cat", cacheDir=str(tmp_path)) == "貓"


def testDamagedCacheIsIgnored(monkeypatch, tmp_path):
    (tmp_path / "zh-TW.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(genAITutor, "connectGenAI", lambda userMessage, **options: "貓")

    assert genAITutor.translateWord("cat", cacheDir=str(tmp_path)) == "貓"


def testEmptyTranslationIsNotCached(monkeypatch, tmp_path):
    monkeypatch.setattr(genAITutor, "connectGenAI", lambda userMessage, **options: "")

    assert genAITutor.translateWord("cat", cacheDir=str(tmp_path)) == ""
    assert not (tmp_path / "zh-TW.json").exists()


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("貓", "貓"),
        ("<think>The user wants...</think>\nTranslation: 貓。", "貓"),
        ("\n\n中文：「含糊不清」\nIt means unclear.", "含糊不清"),
    ],
)
def testCleanTranslation(reply, expected):
    assert genAITutor.cleanTranslation(reply) == expected


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("VERDICT: CORRECT\nFEEDBACK: Nice!", (True, "Nice!")),
        ("VERDICT: INCORRECT\nFEEDBACK: Say 'a cat'.", (False, "Say 'a cat'.")),
        ("**VERDICT:** Correct\n**FEEDBACK:** Good job.", (True, "Good job.")),
        ("<think>hmm</think>VERDICT: INCORRECT", (False, "")),
        ("I think it is fine.", (None, "I think it is fine.")),
    ],
)
def testParseSentenceFeedback(reply, expected):
    assert genAITutor.parseSentenceFeedback(reply) == expected


def testCheckSentenceSendsWordAndSentence(monkeypatch):
    sentMessages = []

    def fakeConnectGenAI(userMessage, **options):
        sentMessages.append(userMessage)
        return "VERDICT: CORRECT\nFEEDBACK: Well done."

    monkeypatch.setattr(genAITutor, "connectGenAI", fakeConnectGenAI)

    assert genAITutor.checkSentence("cat", "a pet", "My cat is cute.") == (
        True,
        "Well done.",
    )
    assert "Target word: cat" in sentMessages[0]
    assert "Student sentence: My cat is cute." in sentMessages[0]


def testParseVocabularyReplyKeepsOnlyWordsInTheText():
    text = "The ending was ambiguous and the readers were reluctant to guess."
    reply = (
        "<think>...</think>\n1. ambiguous - unclear\n- **reluctant**\nserendipity\n"
        "ambiguous\n\nreluctant to guess too long a phrase here"
    )

    assert genAITutor.parseVocabularyReply(reply, text) == ["ambiguous", "reluctant"]


def testParseVocabularyReplyRespectsMaxWords():
    assert genAITutor.parseVocabularyReply(
        "cat\ndog\npig", "cat dog pig", maxWords=2
    ) == ["cat", "dog"]


def testPickVocabularySendsTheText(monkeypatch):
    sentMessages = []

    def fakeConnectGenAI(userMessage, **options):
        sentMessages.append(userMessage)
        return "hypothesis"

    monkeypatch.setattr(genAITutor, "connectGenAI", fakeConnectGenAI)

    assert genAITutor.pickVocabulary("A hypothesis is an idea.") == ["hypothesis"]
    assert "A hypothesis is an idea." in sentMessages[0]


def testIsAiAvailable(monkeypatch):
    assert genAITutor.isAIAvailable() is False

    monkeypatch.setenv("LLM_API_KEY", "test")
    assert genAITutor.isAIAvailable() is True
