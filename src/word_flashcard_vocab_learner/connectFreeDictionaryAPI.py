import requests

def getWordDefinition(requiredWord: str, maxDefinitions: int = 3) -> dict:

    URL = "https://freedictionaryapi.com/api/v1/entries/en/" + requiredWord + "?translations=true"

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

    definitionsFormatted = "\n".join(f"    - {eachDefinition}" for eachDefinition in definitions[:maxDefinitions])
    translationsFormatted = "\n".join(f"    - {eachTranslation}" for eachTranslation in translations)



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

    if (code == "zh" or "Chinese" in name):
        return True
    
    return False

print(getWordDefinition("road"))

