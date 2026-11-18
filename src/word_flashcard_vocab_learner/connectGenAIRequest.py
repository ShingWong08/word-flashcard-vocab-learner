import os
import requests

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

def connectGenAIRequest(
    userMessaage: str,

    baseURL: str = "https://api.deepseek.com/chat/completions",
    apiKey: str | None = None,
    model: str = "deepseek-flash",
    systemMessage: str = "You are an English vocabulary tutor, Return the word, definition, example sentence, and Chinese translation.",
    temperature: float = 1.0,
    top_P: float = 1.0,
    maxTokens: int = 2000,
    stream: bool = False,
    reasoningEffort: str = "low"


) -> str:

    """
        Similar to connectGenAI, but uses 'requests' package to send the request to the GenAI API instead of the OpenAI package.
    """

    resolvedApiKey = apiKey or os.environ.get("LLM_API_KEY")
    if not resolvedApiKey:
        raise RuntimeError(
            "LLM_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + resolvedApiKey,
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": systemMessage},
            {"role": "user", "content": userMessaage},
        ],
        "temperature": temperature,
        "top_p": top_P,
        "max_tokens": maxTokens,
        "stream": stream,
        "reasoning_effort": reasoningEffort,
        "thinking": {"type": "disabled"},
    }

    response = requests.post(baseURL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]

    print(content)

    return content

# print(
#     connectGenAIRequest(
#         "Please provide a list of 10 English vocabulary words with their definitions, example sentences, and Chinese translations."
#     )
# )