import os
from functools import cache
from typing import TYPE_CHECKING

from word_flashcard_vocab_learner.llmSettings import envFloat, envInt, envText

if TYPE_CHECKING:
    from openai import OpenAI

# The openai package retries a failed request twice by default, and waits up to 10
# minutes for each answer. One retry is enough; LLM_TIMEOUT sets the wait.
MAX_RETRIES = 1


@cache
def _client(baseURL: str, apiKey: str) -> "OpenAI":
    """
    One client per API address and key. Reusing it keeps the connection open,
    so translating many words in a row does not start a new HTTPS connection each time.
    The result is cached (functools.cache): the same address and key always give back
    the same client.

    Parameters:
        Mandatory:
            - baseURL (str): The base URL of the OpenAI-compatible API.
            - apiKey (str): The API key.
    Returns:
        OpenAI: The client for that address and key.
    """

    # The openai package takes about a second to import, so it is only loaded
    # the first time the AI tutor is used, not every time the app starts.
    from openai import OpenAI

    return OpenAI(base_url=baseURL, api_key=apiKey, max_retries=MAX_RETRIES)


def connectGenAI(
    userMessage: str,
    baseURL: str | None = None,
    apiKey: str | None = None,
    model: str | None = None,
    systemMessage: str | None = None,
    temperature: float | None = None,
    topP: float | None = None,
    maxTokens: int | None = None,
    timeout: float | None = None,
) -> str:
    """
    Connect to an OpenAI-compatible LLM API (via the OpenAI package) and return the
    generated response.

    There are no built-in defaults. Every optional parameter left as None is read
    from its LLM_* variable in .env, and a missing variable is an error.
    An argument you pass always wins over .env.

    Parameters:
        Mandatory:
            - userMessage (str): The message to send to the AI model.
        Optional (pass it, or set the .env variable after the dash):
            - baseURL (str): LLM API base URL, e.g. "https://host/v1". - LLM_BASE_URL
            - apiKey (str): LLM API key. - LLM_API_KEY
            - model (str): The model to use for generating responses. - LLM_MODEL
            - systemMessage (str): The system message to set the context for the AI
              model. - LLM_SYSTEM_MESSAGE
            - temperature (float): Sampling temperature for response generation.
              - LLM_TEMPERATURE
            - topP (float): Nucleus sampling parameter for response generation.
              - LLM_TOP_P
            - maxTokens (int): Maximum number of tokens to generate in the response.
              - LLM_MAX_TOKENS
            - timeout (float): Seconds to wait for the answer. - LLM_TIMEOUT
              This one may be left out: without it the openai package's own limit
              (10 minutes) is used.
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
    if timeout is None and os.environ.get("LLM_TIMEOUT", "").strip() != "":
        timeout = envFloat("LLM_TIMEOUT", "timeout")

    # Only passed when set, so the openai package's own default stays in place.
    extraOptions = {} if timeout is None else {"timeout": timeout}

    response = _client(baseURL, apiKey).chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": systemMessage},
            {"role": "user", "content": userMessage},
        ],
        temperature=temperature,
        top_p=topP,
        max_tokens=maxTokens,
        **extraOptions,
    )

    return response.choices[0].message.content or ""
