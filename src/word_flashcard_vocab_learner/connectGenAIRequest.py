import os

import requests

TUTOR_SYSTEM_MESSAGE = (
    "You are an English vocabulary tutor. "
    "Return the word, definition, example sentence, and Chinese translation."
)


def connectGenAIRequest(
    userMessage: str,
    baseURL: str = "https://integrate.api.nvidia.com/v1/chat/completions",
    apiKey: str | None = None,
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    systemMessage: str = TUTOR_SYSTEM_MESSAGE,
    temperature: float = 1.0,
    topP: float = 1.0,
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
            - apiKey (str): LLM API key. Falls back to the LLM_API_KEY environment
              variable.
            - Other parameters: same meaning as in connectGenAI.
            - reasoningEffort (str): Reasoning effort hint for the model.
            - timeout (float): Request timeout in seconds.
    """

    if apiKey is None:
        apiKey = os.environ.get("LLM_API_KEY")

    if not apiKey:
        raise RuntimeError(
            "LLM_API_KEY is not configured. Set it in .env or pass apiKey explicitly."
        )

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
        baseURL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {apiKey}",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"] or ""
