import json
import os
import re

from word_flashcard_vocab_learner.connectGenAI import connectGenAI


TRANSLATION_CACHE_DIR = "translation_cache"
TRANSLATION_CACHE_FILE = "zh-TW.json"
MAX_TRANSLATION_LENGTH = 40

TRANSLATION_SYSTEM_MESSAGE = (
    "You are an English-Chinese dictionary for Hong Kong secondary school students. "
    "Translate the English word into Traditional Chinese, using the meaning given. "
    "Reply with only the Chinese translation (a few words at most), "
    "with no pinyin, no quotes and no explanation."
)

SENTENCE_SYSTEM_MESSAGE = (
    "You are a friendly English teacher for secondary school students. "
    "The student writes one sentence using a target word. "
    "Decide whether the target word is used with the right meaning and correct grammar. "
    "Reply in exactly this format:\n"
    "VERDICT: CORRECT or INCORRECT\n"
    "FEEDBACK: one or two short sentences in simple English. "
    "If the sentence is incorrect, include a corrected version."
)


VOCABULARY_SYSTEM_MESSAGE = (
    "You help Hong Kong secondary school students learn English vocabulary. "
    "From the text the user gives you, pick the most useful words or short phrases for a student to learn: "
    "words that are not too basic, appear in the text, and are worth remembering. Skip names of people and places. "
    "Reply with one word or phrase per line, in the form used in the text, with no numbers and no explanation."
)

MAX_TEXT_FOR_AI = 12000
DEFAULT_VOCABULARY_COUNT = 20


def isAIAvailable() -> bool:

    """
    Return True when LLM_API_KEY is set, so translation and sentence feedback can be used.
    """

    return bool(os.environ.get("LLM_API_KEY"))


def stripThinking(text: str) -> str:

    """
    Remove <think>...</think> blocks that some reasoning models put before their answer.
    """

    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def cleanTranslation(reply: str) -> str:

    """
    Turn the model's reply into a short translation:
    keep the first non-empty line, drop labels like "Translation:" and surrounding quotes.
    """

    text = stripThinking(reply)

    firstLine = ""
    for eachLine in text.splitlines():
        if eachLine.strip() != "":
            firstLine = eachLine.strip()
            break

    firstLine = re.sub(r"^(translation|chinese|中文|翻譯)\s*[:：]\s*", "", firstLine, flags=re.IGNORECASE)
    firstLine = firstLine.strip(" \"'「」『』“”。.")

    return firstLine[:MAX_TRANSLATION_LENGTH]


def loadTranslationCache(cachePath: str) -> dict:

    """
    Load the saved translations. Returns an empty dict if the file is missing or damaged.
    """

    if not os.path.exists(cachePath):
        return {}

    try:
        with open(cachePath, encoding="utf-8") as cacheFile:
            data = json.load(cacheFile)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def saveTranslationCache(cache: dict, cachePath: str) -> None:

    folder = os.path.dirname(cachePath)
    if folder != "":
        os.makedirs(folder, exist_ok=True)

    with open(cachePath, "w", encoding="utf-8") as cacheFile:
        json.dump(cache, cacheFile, ensure_ascii=False, indent=2)


def translateWord(
    word: str,
    definition: str = "",
    cacheDir: str = TRANSLATION_CACHE_DIR,
    cacheFileName: str = TRANSLATION_CACHE_FILE,
) -> str:

    """
    Translate an English word into Traditional Chinese with the LLM.
    Translations are saved in translation_cache/zh-TW.json, so each word is only sent to the API once.
    Parameters:
        Mandatory:
            - word (str): The English word.
        Optional:
            - definition (str): The English definition, so the right meaning is translated.
            - cacheDir (str): Folder for the translation cache.
            - cacheFileName (str): File name of the translation cache.
    Returns:
        str: The translation, or "" if the model gave no answer.
    """

    cachePath = os.path.join(cacheDir, cacheFileName)
    cache = loadTranslationCache(cachePath)
    key = word.strip().lower()

    if key in cache:
        return cache[key]

    userMessage = f"Word: {word}\nMeaning: {definition}"
    reply = connectGenAI(userMessage, systemMessage=TRANSLATION_SYSTEM_MESSAGE, temperature=0.2)
    translation = cleanTranslation(reply)

    if translation != "":
        cache[key] = translation
        saveTranslationCache(cache, cachePath)

    return translation


def parseSentenceFeedback(reply: str) -> tuple[bool | None, str]:

    """
    Read the VERDICT and FEEDBACK lines from the model's reply.
    Returns (True / False / None if no verdict was found, feedback text).
    """

    text = stripThinking(reply)

    isCorrect = None
    # [\s*:]* also accepts Markdown bold, e.g. "**VERDICT:** CORRECT"
    verdictMatch = re.search(r"VERDICT[\s*:]*(INCORRECT|CORRECT)", text, flags=re.IGNORECASE)
    if verdictMatch is not None:
        isCorrect = verdictMatch.group(1).upper() == "CORRECT"

    feedbackMatch = re.search(r"FEEDBACK[\s*:]*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
    if feedbackMatch is not None:
        feedback = feedbackMatch.group(1).strip()
    else:
        feedback = re.sub(r".*VERDICT.*", "", text, flags=re.IGNORECASE).strip()

    return isCorrect, feedback


def parseVocabularyReply(reply: str, text: str, maxWords: int = DEFAULT_VOCABULARY_COUNT) -> list[str]:

    """
    Read one word per line from the model's reply.
    Numbers, bullets and explanations after a dash are removed, and only words that really
    appear in the text are kept, so the model cannot invent words.
    """

    loweredText = text.lower()
    words = []
    seen = set()

    for eachLine in stripThinking(reply).splitlines():
        word = re.sub(r"^\s*(\d+\s*[.)]|[-*•])\s*", "", eachLine)
        word = re.split(r"\s+[-–—:]\s+|[(:：]", word, maxsplit=1)[0]
        word = word.strip(" *\"'`.,")

        if word == "" or len(word.split()) > 3:
            continue

        if word.lower() not in loweredText or word.lower() in seen:
            continue

        seen.add(word.lower())
        words.append(word)

        if len(words) >= maxWords:
            break

    return words


def pickVocabulary(text: str, maxWords: int = DEFAULT_VOCABULARY_COUNT) -> list[str]:

    """
    Ask the LLM to pick the most useful words to learn from a passage.
    Only the first MAX_TEXT_FOR_AI characters are sent, to keep the request small.
    """

    shortText = text[:MAX_TEXT_FOR_AI]
    userMessage = f"Pick up to {maxWords} words.\n\nText:\n{shortText}"
    reply = connectGenAI(userMessage, systemMessage=VOCABULARY_SYSTEM_MESSAGE, temperature=0.3)

    return parseVocabularyReply(reply, shortText, maxWords)


def checkSentence(word: str, definition: str, sentence: str) -> tuple[bool | None, str]:

    """
    Ask the LLM whether the student used the word correctly in a sentence.
    Returns (True / False / None if the model's answer could not be read, feedback text).
    """

    userMessage = f"Target word: {word}\nMeaning: {definition}\nStudent sentence: {sentence}"
    reply = connectGenAI(userMessage, systemMessage=SENTENCE_SYSTEM_MESSAGE, temperature=0.3)

    return parseSentenceFeedback(reply)
