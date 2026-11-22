import os

CHAT_COMPLETIONS_PATH = "/chat/completions"


def envText(name: str, parameter: str) -> str:
    """
    Read a required text setting from the environment (.env is loaded when the
    package starts). There is no default: a missing or blank variable is an error.

    Parameters:
        Mandatory:
            - name (str): The environment variable, e.g. "LLM_MODEL".
            - parameter (str): The function parameter that could be passed instead,
              e.g. "model". Only used in the error message.
    Returns:
        str: The variable's value without surrounding spaces.
    Raises:
        RuntimeError: The variable is missing or blank.
    """

    value = os.environ.get(name, "").strip()
    if value == "":
        raise RuntimeError(
            f"{name} is not configured. Set it in .env or pass {parameter} explicitly."
        )

    return value


def envFloat(name: str, parameter: str) -> float:
    """
    Read a required decimal number setting from the environment.

    Parameters:
        Mandatory:
            - name (str): The environment variable, e.g. "LLM_TEMPERATURE".
            - parameter (str): The function parameter that could be passed instead.
    Returns:
        float: The variable's value.
    Raises:
        RuntimeError: The variable is missing or blank.
        ValueError: The variable is not a number.
    """

    value = envText(name, parameter)

    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {value!r}.") from None


def envInt(name: str, parameter: str) -> int:
    """
    Read a required whole number setting from the environment.

    Parameters:
        Mandatory:
            - name (str): The environment variable, e.g. "LLM_MAX_TOKENS".
            - parameter (str): The function parameter that could be passed instead.
    Returns:
        int: The variable's value.
    Raises:
        RuntimeError: The variable is missing or blank.
        ValueError: The variable is not a whole number.
    """

    value = envText(name, parameter)

    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, got {value!r}.") from None


def chatCompletionsURL(baseURL: str) -> str:
    """
    Turn an OpenAI-compatible base URL into its chat completions endpoint.
    A URL that already ends with /chat/completions is kept as it is, so both
    "https://host/v1" and "https://host/v1/chat/completions" work.

    Parameters:
        Mandatory:
            - baseURL (str): The API base URL or the full endpoint.
    Returns:
        str: The chat completions endpoint.
    """

    url = baseURL.rstrip("/")
    if url.endswith(CHAT_COMPLETIONS_PATH):
        return url

    return url + CHAT_COMPLETIONS_PATH
