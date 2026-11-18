from openai import OpenAI

def connectGenAI(
    userMessaage: str,

    baseURL: str = "https://integrate.api.nvidia.com/v1",
    apiKey: str = "NVIDIA_API_KEY",
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    systemMessage: str = "You are an AI assistant.",
    temperature: float = 1.0,
    top_P: float = 1.0,
    maxTokens: int = 2000,
    stream: bool = False,
    
) -> str:
    client = OpenAI(base_url = baseURL, api_key = apiKey)

    response = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": systemMessage},
            {"role": "user", "content": userMessaage},
        ],
        temperature=temperature,
        top_p=top_P,
        max_tokens=maxTokens,
        stream=stream,
    )

    content = response.choices[0].message.content

    return content