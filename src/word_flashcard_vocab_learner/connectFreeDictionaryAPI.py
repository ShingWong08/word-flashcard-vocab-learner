from urllib.parse import quote

import requests

from word_flashcard_vocab_learner import terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor

DICTIONARY_URL = "https://freedictionaryapi.com/api/v1/entries/en/"
HTTP_NOT_FOUND = 404

# One shared connection for every lookup: importing a word list looks up many words in a
# row,
# and reusing the connection skips a new HTTPS handshake for each of them.
session = requests.Session()


def getWordDefinition(
    word: str,
    dictionaryURL: str = DICTIONARY_URL,
    query: str = "",
    maxDefinitions: int = 3,
    maxExamples: int = 2,
    timeout: float = 15,
) -> dict:
    """
    Fetches the definitions and example sentences of a word from the Free Dictionary
    API.
    Parameters:
        Mandatory:
            - word (str): The word for which the definitions are to be fetched.
        Optional:
            - dictionaryURL (str): The base URL of the Free Dictionary API.
            - query (str): Additional query parameters for the API request (e.g.
              "?key=value").
            - maxDefinitions (int): Maximum number of definitions to return.
            - maxExamples (int): Maximum number of example sentences for each
              definition.
            - timeout (float): Request timeout in seconds.
        Default:
            - dictionaryURL: "https://freedictionaryapi.com/api/v1/entries/en/"
            - query: ""
            - maxDefinitions: 3
            - maxExamples: 2
            - timeout: 15
    Returns:
        dict: {"word": str, "definitions": list[str], "examples": list[list[str]]}
        "word" is the spelling the dictionary matched (e.g. "Jason" for "jason").
        examples[i] holds the example sentences of definitions[i] (it can be an empty
        list).
        If the word is not found, "definitions" and "examples" are empty.

    The API is case-sensitive, so the word is tried as typed, then in lowercase,
    then capitalized ("jason" -> "Jason"), and the first match is used.
    """

    word = word.strip()
    if word == "":
        raise ValueError("Word cannot be empty.")

    matchedWord = word
    entries = []

    for eachSpelling in caseVariants(word):
        entries = fetchEntries(eachSpelling, dictionaryURL, query, timeout)

        if entries:
            matchedWord = eachSpelling
            break

    definitions, examples = collectDefinitionsAndExamples(entries)

    return {
        "word": matchedWord,
        "definitions": definitions[:maxDefinitions],
        "examples": [
            eachExamples[:maxExamples] for eachExamples in examples[:maxDefinitions]
        ],
    }


def fetchEntries(word: str, dictionaryURL: str, query: str, timeout: float) -> list:
    """
    Request one spelling from the API and return its entries.
    Returns an empty list if the word is not found.
    """

    response = session.get(
        dictionaryURL + quote(word, safe="") + query, timeout=timeout
    )

    if response.status_code == HTTP_NOT_FOUND:
        return []

    response.raise_for_status()

    entries = response.json().get("entries")
    return [] if entries is None else entries


def collectDefinitionsAndExamples(entries: list) -> tuple[list[str], list[list[str]]]:
    """
    Collect every definition and its example sentences from the entries,
    including sub-senses. The two lists line up: examples[i] belongs to definitions[i].
    """

    definitions = []
    examples = []

    for eachEntry in entries:
        for eachSense in eachEntry.get("senses", []):
            for eachMeaning in [eachSense, *eachSense.get("subsenses", [])]:
                if "definition" in eachMeaning:
                    definitions.append(eachMeaning["definition"])
                    examples.append(eachMeaning.get("examples", []))

    return definitions, examples


def caseVariants(word: str) -> list[str]:
    """
    Spellings to try, in order, without duplicates: as typed, lowercase, capitalized.
    Example: "jason" -> ["jason", "Jason"]
    """

    return list(dict.fromkeys([word, word.lower(), word.capitalize()]))


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

    if not definitions:
        return ChatColor.paint(f'No definition found for "{word}".', ChatColor.ORANGE)

    lines = [
        ChatColor.paint("Definitions of ", ChatColor.BOLD)
        + ChatColor.paint(f'"{word}"', ChatColor.BOLD, ChatColor.VIOLET)
        + ChatColor.paint(":", ChatColor.BOLD)
    ]

    for index, eachDefinition in enumerate(definitions):
        number = f"  {index + 1}. "
        examplePrefix = " " * len(number) + "> "

        lines.append("")
        lines.append(
            terminalDisplay.wrapParagraph(
                eachDefinition, number, prefixStyles=(ChatColor.DARK_GRAY,)
            )
        )

        # A hand-edited card may have fewer example lists than definitions.
        for eachExample in examples[index] if index < len(examples) else []:
            lines.append(
                terminalDisplay.wrapParagraph(
                    eachExample,
                    examplePrefix,
                    prefixStyles=(ChatColor.DARK_GRAY,),
                    textStyles=(ChatColor.AQUA,),
                )
            )

    return "\n".join(lines)


def sendWordDefinition(word: str) -> str:
    return formatWordDefinition(getWordDefinition(word))


if __name__ == "__main__":
    print(sendWordDefinition("banana"))
