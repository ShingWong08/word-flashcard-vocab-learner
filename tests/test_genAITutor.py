import json

import pytest

from word_flashcard_vocab_learner import genAITutor


def noAPICall(*arguments, **keywordArguments):
    raise AssertionError("The API should not be called")


def test_translate_word_calls_ai_and_saves_cache(monkeypatch, tmp_path):
    sentMessages = []

    def fakeConnectGenAI(userMessage, **options):
        sentMessages.append(userMessage)
        return "「含糊不清」"

    monkeypatch.setattr(genAITutor, "connectGenAI", fakeConnectGenAI)

    translation = genAITutor.translateWord("Ambiguous", "open to more than one meaning", cacheDir=str(tmp_path))

    assert translation == "含糊不清"
    assert "open to more than one meaning" in sentMessages[0]

    savedCache = json.loads((tmp_path / "zh-TW.json").read_text(encoding="utf-8"))
    assert savedCache == {"ambiguous": "含糊不清"}

    monkeypatch.setattr(genAITutor, "connectGenAI", noAPICall)
    assert genAITutor.translateWord("ambiguous", cacheDir=str(tmp_path)) == "含糊不清"


def test_translate_word_reads_existing_cache(monkeypatch, tmp_path):
    (tmp_path / "zh-TW.json").write_text('{"cat": "貓"}', encoding="utf-8")
    monkeypatch.setattr(genAITutor, "connectGenAI", noAPICall)

    assert genAITutor.translateWord("cat", cacheDir=str(tmp_path)) == "貓"


def test_damaged_cache_is_ignored(monkeypatch, tmp_path):
    (tmp_path / "zh-TW.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(genAITutor, "connectGenAI", lambda userMessage, **options: "貓")

    assert genAITutor.translateWord("cat", cacheDir=str(tmp_path)) == "貓"


def test_empty_translation_is_not_cached(monkeypatch, tmp_path):
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
def test_clean_translation(reply, expected):
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
def test_parse_sentence_feedback(reply, expected):
    assert genAITutor.parseSentenceFeedback(reply) == expected


def test_check_sentence_sends_word_and_sentence(monkeypatch):
    sentMessages = []

    def fakeConnectGenAI(userMessage, **options):
        sentMessages.append(userMessage)
        return "VERDICT: CORRECT\nFEEDBACK: Well done."

    monkeypatch.setattr(genAITutor, "connectGenAI", fakeConnectGenAI)

    assert genAITutor.checkSentence("cat", "a pet", "My cat is cute.") == (True, "Well done.")
    assert "Target word: cat" in sentMessages[0]
    assert "Student sentence: My cat is cute." in sentMessages[0]


def test_parse_vocabulary_reply_keeps_only_words_in_the_text():
    text = "The ending was ambiguous and the readers were reluctant to guess."
    reply = "<think>...</think>\n1. ambiguous - unclear\n- **reluctant**\nserendipity\nambiguous\n\nreluctant to guess too long a phrase here"

    assert genAITutor.parseVocabularyReply(reply, text) == ["ambiguous", "reluctant"]


def test_parse_vocabulary_reply_respects_max_words():
    assert genAITutor.parseVocabularyReply("cat\ndog\npig", "cat dog pig", maxWords=2) == ["cat", "dog"]


def test_pick_vocabulary_sends_the_text(monkeypatch):
    sentMessages = []

    def fakeConnectGenAI(userMessage, **options):
        sentMessages.append(userMessage)
        return "hypothesis"

    monkeypatch.setattr(genAITutor, "connectGenAI", fakeConnectGenAI)

    assert genAITutor.pickVocabulary("A hypothesis is an idea.") == ["hypothesis"]
    assert "A hypothesis is an idea." in sentMessages[0]


def test_is_ai_available(monkeypatch):
    assert genAITutor.isAIAvailable() is False

    monkeypatch.setenv("LLM_API_KEY", "test")
    assert genAITutor.isAIAvailable() is True
