import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

load_dotenv(find_dotenv(usecwd=True))

def connectGenAI(

    userMessage: str,

    baseURL: str = "https://integrate.api.nvidia.com/v1",
    apiKey: str | None = None,
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    systemMessage: str = "You are an AI assistant.",
    temperature: float = 1.0,
    top_P: float = 1.0,
    maxTokens: int = 2000,

) -> str:

    """
    Connect to an OpenAI-compatible LLM API (via the OpenAI package) and return the generated response.

    Parameters:
        Mandatory:
            - userMessage (str): The message to send to the AI model.
        Optional:
            - baseURL (str): LLM API base URL.
            - apiKey (str): LLM API key. Falls back to the LLM_API_KEY environment variable.
            - model (str): The model to use for generating responses.
            - systemMessage (str): The system message to set the context for the AI model.
            - temperature (float): Sampling temperature for response generation.
            - top_P (float): Nucleus sampling parameter for response generation.
            - maxTokens (int): Maximum number of tokens to generate in the response.
        Default:
            - baseURL: "https://integrate.api.nvidia.com/v1"
            - apiKey: LLM_API_KEY from .env
            - model: "deepseek-ai/deepseek-v4.1-flash"
            - systemMessage: "You are an AI assistant."
            - temperature: 1.0
            - top_P: 1.0
            - maxTokens: 2000
    """

    resolvedApiKey = apiKey or os.environ.get("LLM_API_KEY")
    if not resolvedApiKey:
        raise RuntimeError(
            "LLM_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    client = OpenAI(base_url=baseURL, api_key=resolvedApiKey)

    response = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": systemMessage},
            {"role": "user", "content": userMessage},
        ],
        temperature=temperature,
        top_p=top_P,
        max_tokens=maxTokens,
    )

    return response.choices[0].message.content or ""
