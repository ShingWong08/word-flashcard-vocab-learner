from openai import OpenAI

def connect_to_ai(
    user_message: str,

    base_url: str = "https://integrate.api.nvidia.com/v1",
    api_key: str = "NVIDIA_API_KEY",
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    system_message: str = "You are an AI assistant.",
    temperature: float = 1.0,
    top_p: float = 1.0,
    max_tokens: int = 2000,
    stream: bool = False,
) -> str:
    client = OpenAI(base_url=base_url, api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stream=stream,
    )

    content = response.choices[0].message.content

    return content
