import os

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))


def connectGenAIRequest(
    userMessage: str,

    baseURL: str = "https://integrate.api.nvidia.com/v1/chat/completions",
    apiKey: str | None = None,
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    systemMessage: str = "You are an English vocabulary tutor. Return the word, definition, example sentence, and Chinese translation.",
    temperature: float = 1.0,
    top_P: float = 1.0,
    maxTokens: int = 2000,
    reasoningEffort: str = "low",
    timeout: float = 60,
) -> str:

    """
    Similar to connectGenAI, but calls the LLM API directly with the 'requests' package
    instead of the OpenAI package.

    Parameters:
        Mandatory:
            - userMessage (str): The message to send to the AI model.
        Optional:
            - apiKey (str): LLM API key. Falls back to the LLM_API_KEY environment variable.
            - Other parameters: same meaning as in connectGenAI.
            - reasoningEffort (str): Reasoning effort hint for the model.
            - timeout (float): Request timeout in seconds.
    """

    if apiKey is None:
        apiKey = os.environ.get("LLM_API_KEY")

    if not apiKey:
        raise RuntimeError(
            "LLM_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + apiKey,
    }

    messages = [
        {"role": "system", "content": systemMessage},
        {"role": "user", "content": userMessage},
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_P,
        "max_tokens": maxTokens,
        "stream": False,
        "reasoning_effort": reasoningEffort,
        "thinking": {"type": "disabled"},
    }

    response = requests.post(baseURL, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    content = data["choices"][0]["message"]["content"]
    if content is None:
        return ""

    return content
