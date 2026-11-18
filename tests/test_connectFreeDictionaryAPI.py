import pytest
import requests

from word_flashcard_vocab_learner import connectFreeDictionaryAPI as dictionary


class FakeResponse:
    def __init__(self, data=None, status_code=200):
        if data is None:
            data = {}

        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


SAMPLE = {
    "entries": [
        {
            "senses": [
                {
                    "definition": "def 1",
                    "examples": ["ex 1 first", "ex 1 second", "ex 1 third"],
                    "subsenses": [{"definition": "def 1a", "examples": ["ex 1a"]}],
                },
                {"definition": "def 2"},
                {"subsenses": []},
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


def test_collects_definitions_and_matching_examples(capturedURL):
    result = dictionary.getWordDefinition("example")

    assert result == {
        "word": "example",
        "definitions": ["def 1", "def 1a", "def 2"],
        "examples": [["ex 1 first", "ex 1 second"], ["ex 1a"], []],
    }
    assert capturedURL["timeout"] == 15


def test_respects_max_examples_per_definition(capturedURL):
    result = dictionary.getWordDefinition("example", maxExamplesPerDefinition=3)
    assert result["examples"][0] == ["ex 1 first", "ex 1 second", "ex 1 third"]


def test_does_not_request_translations(capturedURL):
    dictionary.getWordDefinition("example")
    assert capturedURL["url"] == "https://freedictionaryapi.com/api/v1/entries/en/example"


def test_respects_max_definitions(capturedURL):
    result = dictionary.getWordDefinition("example", maxDefinitions=1)
    assert result["definitions"] == ["def 1"]
    assert result["examples"] == [["ex 1 first", "ex 1 second"]]


def test_word_is_url_encoded(capturedURL):
    dictionary.getWordDefinition("  ice cream/x ")
    assert capturedURL["url"].endswith("/en/ice%20cream%2Fx")


def test_not_found_returns_empty_result(capturedURL):
    capturedURL["response"] = FakeResponse(status_code=404)
    result = dictionary.getWordDefinition("qwzx")
    assert result == {"word": "qwzx", "definitions": [], "examples": []}
    assert dictionary.formatWordDefinition(result) == 'No definition found for "qwzx".'


def test_server_error_raises(capturedURL):
    capturedURL["response"] = FakeResponse(status_code=500)
    with pytest.raises(requests.HTTPError):
        dictionary.getWordDefinition("example")


def test_empty_word_raises():
    with pytest.raises(ValueError):
        dictionary.getWordDefinition("   ")


def test_case_variants():
    assert dictionary.caseVariants("jason") == ["jason", "Jason"]
    assert dictionary.caseVariants("BOOK") == ["BOOK", "book", "Book"]
    assert dictionary.caseVariants("cat") == ["cat", "Cat"]


def test_falls_back_to_capitalized_spelling(monkeypatch):
    requested = []

    def fakeGet(url, timeout):
        requested.append(url)
        if url.endswith("/en/Jason"):
            return FakeResponse({"entries": [{"senses": [{"definition": "A male given name."}]}]})
        return FakeResponse({"word": "x", "entries": []})  # API answers 200 with no entries

    monkeypatch.setattr(dictionary.requests, "get", fakeGet)
    result = dictionary.getWordDefinition("jason")

    assert result == {"word": "Jason", "definitions": ["A male given name."], "examples": [[]]}
    assert [url.rsplit("/", 1)[1] for url in requested] == ["jason", "Jason"]


def test_typed_spelling_wins_when_it_exists(capturedURL):
    result = dictionary.getWordDefinition("Example")
    assert result["word"] == "Example"
    assert capturedURL["url"].endswith("/en/Example")


def test_format_word_definition_with_examples():
    text = dictionary.formatWordDefinition({
        "word": "cat",
        "definitions": ["a small animal", "a person"],
        "examples": [["The cat sat on the mat.", "I have two cats."], []],
    })

    assert text == "\n".join([
        'Definitions of "cat":',
        "",
        "  1. a small animal",
        "     > The cat sat on the mat.",
        "     > I have two cats.",
        "",
        "  2. a person",
    ])


def test_format_word_definition_wraps_long_lines(monkeypatch):
    monkeypatch.setenv("COLUMNS", "40")
    longDefinition = "The elongated curved tropical fruit of a banana plant, which grows in bunches."

    text = dictionary.formatWordDefinition({"word": "banana", "definitions": [longDefinition], "examples": [[]]})
    lines = text.splitlines()

    assert lines[2] == "  1. The elongated curved tropical fruit"
    assert lines[3].startswith("     of a banana plant")
    assert all(len(eachLine) <= 40 for eachLine in lines)
