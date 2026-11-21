from urllib.parse import quote

import requests

from word_flashcard_vocab_learner import terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor


HTTP_NOT_FOUND = 404


def getWordDefinition(
    requiredWord: str,
    dictionaryURL: str = "https://freedictionaryapi.com/api/v1/entries/en/",
    otherArguments: str = "",
    maxDefinitions: int = 3,
    maxExamplesPerDefinition: int = 2,
    timeout: float = 15,
) -> dict:

    """
    Fetches the definitions and example sentences of a word from the Free Dictionary API.
    Parameters:
        Mandatory:
            - requiredWord (str): The word for which the definitions are to be fetched.
        Optional:
            - dictionaryURL (str): The base URL of the Free Dictionary API.
            - otherArguments (str): Additional query parameters for the API request (e.g. "?key=value").
            - maxDefinitions (int): Maximum number of definitions to return.
            - maxExamplesPerDefinition (int): Maximum number of example sentences for each definition.
            - timeout (float): Request timeout in seconds.
        Default:
            - dictionaryURL: "https://freedictionaryapi.com/api/v1/entries/en/"
            - otherArguments: ""
            - maxDefinitions: 3
            - maxExamplesPerDefinition: 2
            - timeout: 15
    Returns:
        dict: {"word": str, "definitions": list[str], "examples": list[list[str]]}
        "word" is the spelling the dictionary matched (e.g. "Jason" for "jason").
        examples[i] holds the example sentences of definitions[i] (it can be an empty list).
        If the word is not found, "definitions" and "examples" are empty.

    The API is case-sensitive, so the word is tried as typed, then in lowercase,
    then capitalized ("jason" -> "Jason"), and the first match is used.
    """

    word = requiredWord.strip()
    if word == "":
        raise ValueError("Word cannot be empty.")

    matchedWord = word
    entries = []

    for eachSpelling in caseVariants(word):
        entries = fetchEntries(eachSpelling, dictionaryURL, otherArguments, timeout)

        if len(entries) > 0:
            matchedWord = eachSpelling
            break

    allDefinitions, allExamples = collectDefinitionsAndExamples(entries)

    definitions = allDefinitions[:maxDefinitions]
    examples = []

    for eachExampleList in allExamples[:maxDefinitions]:
        examples.append(eachExampleList[:maxExamplesPerDefinition])

    return {
        "word": matchedWord,
        "definitions": definitions,
        "examples": examples,
    }


def fetchEntries(word: str, dictionaryURL: str, otherArguments: str, timeout: float) -> list:

    """
    Request one spelling from the API and return its entries.
    Returns an empty list if the word is not found.
    """

    URL = dictionaryURL + quote(word, safe="") + otherArguments

    response = requests.get(URL, timeout=timeout)

    if response.status_code == HTTP_NOT_FOUND:
        return []

    response.raise_for_status()
    data = response.json()

    entries = data.get("entries")
    if entries is None:
        return []

    return entries


def collectDefinitionsAndExamples(entries: list) -> tuple[list[str], list[list[str]]]:

    """
    Collect every definition and its example sentences from the entries,
    including sub-senses. The two lists line up: examples[i] belongs to definitions[i].
    """

    definitions = []
    examples = []

    for eachEntry in entries:
        for eachSense in eachEntry.get("senses", []):

            meanings = [eachSense] + eachSense.get("subsenses", [])

            for eachMeaning in meanings:
                if "definition" in eachMeaning:
                    definitions.append(eachMeaning["definition"])
                    examples.append(eachMeaning.get("examples", []))

    return definitions, examples


def caseVariants(word: str) -> list[str]:

    """
    Spellings to try, in order, without duplicates: as typed, lowercase, capitalized.
    Example: "jason" -> ["jason", "Jason"]
    """

    variants = []

    for eachSpelling in [word, word.lower(), word.capitalize()]:
        if eachSpelling not in variants:
            variants.append(eachSpelling)

    return variants


def formatWordDefinition(result: dict) -> str:

    """
    Format the dict returned by getWordDefinition into readable text.
    Definitions are numbered, long lines are wrapped to the screen width,
    and a blank line separates each definition (with its examples) from the next.

    Example:
        Definitions of "cat":

          1. A small domesticated carnivorous mammal.
             > The cat sat on the mat.

          2. A person.
    """

    word = result["word"]
    definitions = result["definitions"]
    examples = result["examples"]

    if len(definitions) == 0:
        return ChatColor.paint(f'No definition found for "{word}".', ChatColor.ORANGE)

    titleStart = ChatColor.paint("Definitions of ", ChatColor.BOLD)
    titleWord = ChatColor.paint(f'"{word}"', ChatColor.BOLD, ChatColor.VIOLET)
    titleEnd = ChatColor.paint(":", ChatColor.BOLD)

    lines = [titleStart + titleWord + titleEnd]

    for index, eachDefinition in enumerate(definitions):
        number = f"  {index + 1}. "
        exampleIndent = " " * len(number)

        lines.append("")
        lines.append(terminalDisplay.wrapParagraph(eachDefinition, number, prefixStyles=(ChatColor.DARK_GRAY,)))

        # A hand-edited card may have fewer example lists than definitions.
        eachExamples = examples[index] if index < len(examples) else []

        for eachExample in eachExamples:
            lines.append(terminalDisplay.wrapParagraph(
                eachExample,
                exampleIndent + "> ",
                prefixStyles=(ChatColor.DARK_GRAY,),
                textStyles=(ChatColor.AQUA,),
            ))

    return "\n".join(lines)

def sendWordDefinition(word: str):
    return formatWordDefinition(getWordDefinition(word))


if __name__ == "__main__":
    print(sendWordDefinition("banana"))