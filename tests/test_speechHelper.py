import importlib.util

import pytest

from word_flashcard_vocab_learner import speechHelper


def testAudioFileName():
    assert speechHelper.audioFileName("Ice Cream") == "ice_cream.mp3"
    assert speechHelper.audioFileName("well-known") == "well_known.mp3"
    assert speechHelper.audioFileName("???") == "word.mp3"


def testSpeechNeedsApiKey():
    assert speechHelper.isSpeechAvailable() is False


def testSpeechNeedsSpeechExtra(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert speechHelper.isSpeechAvailable() is False

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert speechHelper.isSpeechAvailable() is True


def testPronounceReplaysCachedAudio(monkeypatch, tmp_path):
    playModule = pytest.importorskip("elevenlabs.play")
    from word_flashcard_vocab_learner import textToSpeech

    (tmp_path / "cat.mp3").write_bytes(b"cached audio")
    played = []

    def failToGenerate(*arguments, **keywordArguments):
        raise AssertionError("Cached audio should be reused")

    monkeypatch.setattr(playModule, "play", lambda audio: played.append(audio))
    monkeypatch.setattr(textToSpeech, "textToSpeech", failToGenerate)

    speechHelper.pronounce("Cat", cacheDir=str(tmp_path))

    assert played == [b"cached audio"]


def testPronounceGeneratesAudioTheFirstTime(monkeypatch, tmp_path):
    pytest.importorskip("elevenlabs.play")
    from word_flashcard_vocab_learner import textToSpeech

    calls = []
    monkeypatch.setattr(
        textToSpeech,
        "textToSpeech",
        lambda text, **options: calls.append((text, options)),
    )

    speechHelper.pronounce("ice cream", cacheDir=str(tmp_path))

    assert calls == [
        (
            "ice cream",
            {
                "outputFileName": "ice_cream.mp3",
                "outputDir": str(tmp_path),
                "autoPlay": True,
            },
        )
    ]
