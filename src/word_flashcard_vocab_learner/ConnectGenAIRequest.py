import requests

def connectGenAI(
    userMessaage: str,

    baseURL: str = "https://api.deepseek.com/chat/completions",
    apiKey: str = "DEEPSEEK_API_KEY",
    model: str = "deepseek-flash",
    systemMessage: str = "You are an AI assistant.",
    temperature: float = 1.0,
    top_P: float = 1.0,
    maxTokens: int = 2000,
    stream: bool = False,
    reasoningEffort: str = "low"


) -> str:

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + apiKey,
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

    data = requests.post(baseURL, headers = headers, json = payload).json()
    content = data["choices"][0]["message"]["content"]

    print(content)

    return content


connectGenAI("Hello World!")