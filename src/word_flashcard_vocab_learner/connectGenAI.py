import os
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


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

    return OpenAI(base_url=baseURL, api_key=apiKey)


def connectGenAI(
    userMessage: str,
    baseURL: str = "https://integrate.api.nvidia.com/v1",
    apiKey: str | None = None,
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    systemMessage: str = "You are an AI assistant.",
    temperature: float = 1.0,
    topP: float = 1.0,
    maxTokens: int = 2000,
) -> str:
    """
    Connect to an OpenAI-compatible LLM API (via the OpenAI package) and return the
    generated response.

    Parameters:
        Mandatory:
            - userMessage (str): The message to send to the AI model.
        Optional:
            - baseURL (str): LLM API base URL.
            - apiKey (str): LLM API key. Falls back to the LLM_API_KEY environment
              variable.
            - model (str): The model to use for generating responses.
            - systemMessage (str): The system message to set the context for the AI
              model.
            - temperature (float): Sampling temperature for response generation.
            - topP (float): Nucleus sampling parameter for response generation.
            - maxTokens (int): Maximum number of tokens to generate in the response.
        Default:
            - baseURL: "https://integrate.api.nvidia.com/v1"
            - apiKey: LLM_API_KEY from .env
            - model: "deepseek-ai/deepseek-v4.1-flash"
            - systemMessage: "You are an AI assistant."
            - temperature: 1.0
            - topP: 1.0
            - maxTokens: 2000
    """

    if apiKey is None:
        apiKey = os.environ.get("LLM_API_KEY")

    if not apiKey:
        raise RuntimeError(
            "LLM_API_KEY is not configured. Set it in .env or pass apiKey explicitly."
        )

    response = _client(baseURL, apiKey).chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": systemMessage},
            {"role": "user", "content": userMessage},
        ],
        temperature=temperature,
        top_p=topP,
        max_tokens=maxTokens,
    )

    return response.choices[0].message.content or ""
