import pytest

from word_flashcard_vocab_learner import connectGenAI, connectGenAIRequest
from word_flashcard_vocab_learner.llmSettings import (
    chatCompletionsURL,
    envFloat,
    envText,
)


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


@pytest.fixture
def capturePost(monkeypatch):
    """
    Replace requests.post in connectGenAIRequest and return what it was called with.
    """

    calls = {}

    def fakePost(url, headers, json, timeout):
        calls.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(connectGenAIRequest.requests, "post", fakePost)
    return calls


def testChatCompletionsUrlAddsPathOnce():
    expected = "https://host/v1/chat/completions"

    assert chatCompletionsURL("https://host/v1") == expected
    assert chatCompletionsURL("https://host/v1/") == expected
    assert chatCompletionsURL(expected) == expected


def testEnvTextRequiresValue(monkeypatch):
    with pytest.raises(RuntimeError, match="LLM_MODEL is not configured.*model"):
        envText("LLM_MODEL", "model")

    monkeypatch.setenv("LLM_MODEL", "   ")
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        envText("LLM_MODEL", "model")


def testEnvFloatRejectsText(monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "warm")

    with pytest.raises(ValueError, match="LLM_TEMPERATURE"):
        envFloat("LLM_TEMPERATURE", "temperature")


@pytest.mark.parametrize(
    "missing",
    [
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_SYSTEM_MESSAGE",
        "LLM_TEMPERATURE",
        "LLM_TOP_P",
        "LLM_MAX_TOKENS",
        "LLM_REASONING_EFFORT",
        "LLM_TIMEOUT",
    ],
)
def testRequestNeedsEverySetting(monkeypatch, enableAI, capturePost, missing):
    monkeypatch.delenv(missing)

    with pytest.raises(RuntimeError, match=missing):
        connectGenAIRequest.connectGenAIRequest("hi")

    assert capturePost == {}


def testRequestReadsEnv(enableAI, capturePost):
    reply = connectGenAIRequest.connectGenAIRequest("hi")
    payload = capturePost["json"]

    assert reply == "ok"
    assert capturePost["url"] == "https://example.test/v1/chat/completions"
    assert capturePost["headers"]["Authorization"] == "Bearer test"
    assert payload["model"] == "test-model"
    assert payload["messages"][0]["content"] == "Test system message."
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["max_tokens"] == 500
    assert payload["reasoning_effort"] == "low"
    assert capturePost["timeout"] == 30


def testRequestArgumentsNeedNoEnv(capturePost):
    connectGenAIRequest.connectGenAIRequest(
        "hi",
        baseURL="https://other.test/v1/chat/completions",
        apiKey="key",
        model="arg-model",
        systemMessage="Be brief.",
        temperature=0,
        topP=1,
        maxTokens=10,
        reasoningEffort="high",
        timeout=5,
    )

    assert capturePost["url"] == "https://other.test/v1/chat/completions"
    assert capturePost["json"]["model"] == "arg-model"
    assert capturePost["json"]["temperature"] == 0


def testConnectGenAIReadsEnv(monkeypatch, enableAI):
    sent = {}

    class FakeCompletions:
        def create(self, **options):
            sent.update(options)
            message = type("Message", (), {"content": "ok"})
            choice = type("Choice", (), {"message": message})
            return type("Response", (), {"choices": [choice]})

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})

    def fakeClient(baseURL, apiKey):
        sent["baseURL"] = baseURL
        return FakeClient()

    monkeypatch.setattr(connectGenAI, "_client", fakeClient)

    assert connectGenAI.connectGenAI("hi", temperature=0.2) == "ok"
    assert sent["baseURL"] == "https://example.test/v1"
    assert sent["model"] == "test-model"
    assert sent["max_tokens"] == 500
    assert sent["temperature"] == 0.2
    assert sent["top_p"] == 0.9


def testConnectGenAINeedsModel(monkeypatch, enableAI):
    monkeypatch.delenv("LLM_MODEL")

    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        connectGenAI.connectGenAI("hi")
