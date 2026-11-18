from urllib.parse import quote

import requests


def getWordDefinition(
    requiredWord: str,
    dictionaryURL: str = "https://freedictionaryapi.com/api/v1/entries/en/",
    otherArguments: str = "?translations=true",
    maxDefinitions: int = 3,
    maxTranslations: int = 3,
    timeout: float = 15,
) -> dict:

    """
    Fetches the definitions and Chinese translations of a word from the Free Dictionary API.
    Parameters:
        Mandatory:
            - requiredWord (str): The word for which the definition and translation are to be fetched.
        Optional:
            - dictionaryURL (str): The base URL of the Free Dictionary API.
            - otherArguments (str): Additional query parameters for the API request.
            - maxDefinitions (int): Maximum number of definitions to return.
            - maxTranslations (int): Maximum number of Chinese translations to return.
            - timeout (float): Request timeout in seconds.
        Default:
            - dictionaryURL: "https://freedictionaryapi.com/api/v1/entries/en/"
            - otherArguments: "?translations=true"
            - maxDefinitions: 3
            - maxTranslations: 3
            - timeout: 15
    Returns:
        dict: {"word": str, "definitions": list[str], "translations": list[str]}
        If the word is not found, both lists are empty.
    """

    word = requiredWord.strip()
    if not word:
        raise ValueError("Word cannot be empty.")

    URL = dictionaryURL + quote(word, safe="") + otherArguments

    response = requests.get(URL, timeout=timeout)
    if response.status_code == 404:
        return {"word": word, "definitions": [], "translations": []}
    response.raise_for_status()
    data = response.json()

    definitions = []
    translations = []

    def collectTranslations(sense: dict) -> None:
        for eachTranslation in sense.get("translations", []):
            translatedWord = eachTranslation.get("word")
            if (
                translatedWord
                and isChinese(eachTranslation)
                and translatedWord not in translations
            ):
                translations.append(translatedWord)

    for eachEntry in data.get("entries", []):
        for eachSense in eachEntry.get("senses", []):

            if "definition" in eachSense:
                definitions.append(eachSense["definition"])
            collectTranslations(eachSense)

            for eachSubSense in eachSense.get("subsenses", []):
                if "definition" in eachSubSense:
                    definitions.append(eachSubSense["definition"])
                collectTranslations(eachSubSense)

    return {
        "word": word,
        "definitions": definitions[:maxDefinitions],
        "translations": translations[:maxTranslations],
    }


def formatWordDefinition(result: dict) -> str:

    """
    Format the dict returned by getWordDefinition into readable text.
    """

    word = result["word"]
    if not result["definitions"] and not result["translations"]:
        return f'No definition found for "{word}".'

    lines = [f'Definitions of "{word}":']
    lines += [f"  - {eachDefinition}" for eachDefinition in result["definitions"]]
    lines += ["", "Translation:"]
    if result["translations"]:
        lines += [f"  - {eachTranslation}" for eachTranslation in result["translations"]]
    else:
        lines.append("  (none found)")
    return "\n".join(lines)


def isChinese(translation: dict) -> bool:
    language = translation.get("language") or {}
    code = language.get("code") or ""
    name = language.get("name") or ""

    return code == "zh" or code.startswith("zh-") or "Chinese" in name


if __name__ == "__main__":
    print(getWordDefinition("example"))
    print(formatWordDefinition(getWordDefinition("example")))
