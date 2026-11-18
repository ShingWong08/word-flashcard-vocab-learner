import pytest
import requests

from word_flashcard_vocab_learner import connectFreeDictionaryAPI as dictionary


class FakeResponse:
    def __init__(self, data=None, status_code=200):
        self._data = data or {}
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def zh(word):
    return {"language": {"code": "zh", "name": "Chinese"}, "word": word}


SAMPLE = {
    "entries": [
        {
            "senses": [
                {
                    "definition": "def 1",
                    "translations": [
                        {"language": {"code": "fr", "name": "French"}, "word": "exemple"},
                        zh("例子"),
                    ],
                    "subsenses": [
                        {"definition": "def 1a", "translations": [zh("範例"), zh("例子")]},
                    ],
                },
                {"definition": "def 2", "translations": [{"word": "no language"}]},
            ]
        }
    ]
}


@pytest.fixture
def capturedURL(monkeypatch):
    captured = {}

    def fakeGet(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return captured.get("response", FakeResponse(SAMPLE))

    monkeypatch.setattr(dictionary.requests, "get", fakeGet)
    return captured


def test_collects_definitions_and_deduplicated_chinese_translations(capturedURL):
    result = dictionary.getWordDefinition("example")

    assert result == {
        "word": "example",
        "definitions": ["def 1", "def 1a", "def 2"],
        "translations": ["例子", "範例"],
    }
    assert capturedURL["timeout"] == 15


def test_respects_max_definitions(capturedURL):
    result = dictionary.getWordDefinition("example", maxDefinitions=1)
    assert result["definitions"] == ["def 1"]


def test_word_is_url_encoded(capturedURL):
    dictionary.getWordDefinition("  ice cream/x ")
    assert "/en/ice%20cream%2Fx?" in capturedURL["url"]


def test_not_found_returns_empty_result(capturedURL):
    capturedURL["response"] = FakeResponse(status_code=404)
    result = dictionary.getWordDefinition("qwzx")
    assert result == {"word": "qwzx", "definitions": [], "translations": []}
    assert dictionary.formatWordDefinition(result) == 'No definition found for "qwzx".'


def test_server_error_raises(capturedURL):
    capturedURL["response"] = FakeResponse(status_code=500)
    with pytest.raises(requests.HTTPError):
        dictionary.getWordDefinition("example")


def test_empty_word_raises():
    with pytest.raises(ValueError):
        dictionary.getWordDefinition("   ")


@pytest.mark.parametrize(
    "translation, expected",
    [
        (zh("例子"), True),
        ({"language": {"code": "zh-Hant", "name": None}}, True),
        ({"language": {"code": "cmn", "name": "Mandarin Chinese"}}, True),
        ({"language": {"code": "fr", "name": "French"}}, False),
        ({"language": None}, False),
        ({}, False),
    ],
)
def test_isChinese(translation, expected):
    assert dictionary.isChinese(translation) is expected


def test_format_word_definition():
    text = dictionary.formatWordDefinition(
        {"word": "cat", "definitions": ["a small animal"], "translations": []}
    )
    assert 'Definitions of "cat":' in text
    assert "  - a small animal" in text
    assert "(none found)" in text
