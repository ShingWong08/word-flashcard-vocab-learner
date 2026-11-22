import requests

from word_flashcard_vocab_learner.llmSettings import (
    chatCompletionsURL,
    envFloat,
    envInt,
    envText,
)

TUTOR_SYSTEM_MESSAGE = (
    "You are an English vocabulary tutor. "
    "Return the word, definition, example sentence, and Chinese translation."
)


def connectGenAIRequest(
    userMessage: str,
    baseURL: str | None = None,
    apiKey: str | None = None,
    model: str | None = None,
    systemMessage: str | None = None,
    temperature: float | None = None,
    topP: float | None = None,
    maxTokens: int | None = None,
    reasoningEffort: str | None = None,
    timeout: float | None = None,
) -> str:
    """
    Similar to connectGenAI, but calls the LLM API directly with the 'requests' package
    instead of the OpenAI package.

    There are no built-in defaults. Every optional parameter left as None is read
    from its LLM_* variable in .env, and a missing variable is an error.
    An argument you pass always wins over .env.

    Parameters:
        Mandatory:
            - userMessage (str): The message to send to the AI model.
        Optional (pass it, or set the .env variable after the dash):
            - baseURL (str): API base URL ("https://host/v1") or the full chat
              completions endpoint. - LLM_BASE_URL
            - apiKey (str): LLM API key. - LLM_API_KEY
            - model (str): The model name. - LLM_MODEL
            - systemMessage (str): The system message, e.g. TUTOR_SYSTEM_MESSAGE.
              - LLM_SYSTEM_MESSAGE
            - temperature (float): Sampling temperature. - LLM_TEMPERATURE
            - topP (float): Nucleus sampling. - LLM_TOP_P
            - maxTokens (int): Most tokens in the reply. - LLM_MAX_TOKENS
            - reasoningEffort (str): Reasoning effort hint for the model.
              - LLM_REASONING_EFFORT
            - timeout (float): Request timeout in seconds. - LLM_TIMEOUT
    Raises:
        RuntimeError: A setting is neither passed nor set in .env.
        ValueError: A numeric LLM_* variable is not a number.
    """

    if apiKey is None:
        apiKey = envText("LLM_API_KEY", "apiKey")
    if baseURL is None:
        baseURL = envText("LLM_BASE_URL", "baseURL")
    if model is None:
        model = envText("LLM_MODEL", "model")
    if systemMessage is None:
        systemMessage = envText("LLM_SYSTEM_MESSAGE", "systemMessage")
    if temperature is None:
        temperature = envFloat("LLM_TEMPERATURE", "temperature")
    if topP is None:
        topP = envFloat("LLM_TOP_P", "topP")
    if maxTokens is None:
        maxTokens = envInt("LLM_MAX_TOKENS", "maxTokens")
    if reasoningEffort is None:
        reasoningEffort = envText("LLM_REASONING_EFFORT", "reasoningEffort")
    if timeout is None:
        timeout = envFloat("LLM_TIMEOUT", "timeout")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": systemMessage},
            {"role": "user", "content": userMessage},
        ],
        "temperature": temperature,
        "top_p": topP,
        "max_tokens": maxTokens,
        "stream": False,
        "reasoning_effort": reasoningEffort,
        "thinking": {"type": "disabled"},
    }

    response = requests.post(
        chatCompletionsURL(baseURL),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {apiKey}",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"] or ""
