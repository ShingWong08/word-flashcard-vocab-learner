import requests


def getWordDefinition(
    requiredWord: str,
    dictionaryURL: str = "https://freedictionaryapi.com/api/v1/entries/en/",
    otherArguments: str = "?translations=true",
    maxDefinitions: int = 3,
) -> dict:

    """
    Fetches the definition and translation of a word from the Free Dictionary API.
    Parameters:
        Mandatory:
            - requiredWord (str): The word for which the definition and translation are to be fetched.
        Optional:
            - dictionaryURL (str): The base URL of the Free Dictionary API.
            - otherArguments (str): Additional query parameters for the API request.
            - maxDefinitions (int): Maximum number of definitions to return.
        Default:
            - dictionaryURL: "https://freedictionaryapi.com/api/v1/entries/en/"
            - otherArguments: "?translations=true"
            - maxDefinitions: 3
    """


    URL = dictionaryURL + requiredWord + otherArguments

    response = requests.get(URL).json()

    definitions = []
    translations = []
    for eachEntry in response.get("entries", []):
        for eachSense in eachEntry.get("senses", []):

            if "definition" in eachSense:
                definitions.append(eachSense["definition"])

            for eachSubSense in eachSense.get("subsenses", []):
                if "definition" in eachSubSense:
                    definitions.append(eachSubSense["definition"])

                for eachTranslation in eachSubSense.get("translations", []):
                    if not translations and isChinese(eachTranslation):
                        translations.append(eachTranslation.get("word"))

    definitionsFormatted = "\n".join(
        f"    - {eachDefinition}" for eachDefinition in definitions[:maxDefinitions]
    )
    translationsFormatted = "\n".join(
        f"    - {eachTranslation}" for eachTranslation in translations
    )

    return f"""
    Definitions of "{requiredWord}":
{definitionsFormatted}

    Translate: 
{translationsFormatted}
    """


def isChinese(translation: dict) -> bool:
    language = translation.get("language")
    code = language.get("code")
    name = language.get("name")

    if code == "zh" or "Chinese" in name:
        return True

    return False

