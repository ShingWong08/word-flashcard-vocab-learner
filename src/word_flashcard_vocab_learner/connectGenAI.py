import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

load_dotenv(find_dotenv())

def connectGenAI(
        
    userMessaage: str,

    baseURL: str = "https://integrate.api.nvidia.com/v1",
    apiKey: str | None = None,
    model: str = "deepseek-ai/deepseek-v4.1-flash",
    systemMessage: str = "You are an AI assistant.",
    temperature: float = 1.0,
    top_P: float = 1.0,
    maxTokens: int = 2000,
    stream: bool = False,
    
) -> str:

    """
    Connect to the AI model with custom parameters and return the generated response.

    Parameters:
        Mandatory:
            - userMessaage (str): The message to send to the AI model.
        Optional:
            - baseURL (str): LLM API base URL.
            - apiKey (str): LLM API key.
            - model (str): The model to use for generating responses.
            - systemMessage (str): The system message to set the context for the AI model.
            - temperature (float): Sampling temperature for response generation.
            - top_P (float): Nucleus sampling parameter for response generation.
            - maxTokens (int): Maximum number of tokens to generate in the response.
            - stream (bool): Whether to stream the response or not.
        Default:
            - baseURL: "https://integrate.api.nvidia.com/v1"
            - apiKey: "NVIDIA_API_KEY"
            - model: "deepseek-ai/deepseek-v4.1-flash"
            - systemMessage: "You are an AI assistant."
            - temperature: 1.0
            - top_P: 1.0
            - maxTokens: 2000
            - stream: False
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
            {"role": "user", "content": userMessaage},
        ],
        temperature=temperature,
        top_p=top_P,
        max_tokens=maxTokens,
        stream=stream,
    )

    content = response.choices[0].message.content

    return content

# print(
#     connectGenAI(
#         "Please provide a list of 10 English vocabulary words with their definitions, example sentences, and Chinese translations."
#     )
# )