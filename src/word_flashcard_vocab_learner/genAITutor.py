import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from word_flashcard_vocab_learner.connectGenAI import connectGenAI

TRANSLATION_CACHE_DIR = "translation_cache"
TRANSLATION_CACHE_FILE = "zh-TW.json"
MAX_TRANSLATION_LENGTH = 40
MAX_TEXT_FOR_AI = 12000
DEFAULT_VOCABULARY_COUNT = 20
# translateWords sends this many words in one request, and runs up to
# MAX_TRANSLATION_REQUESTS requests at the same time.
TRANSLATION_BATCH_SIZE = 20
MAX_TRANSLATION_REQUESTS = 4

# The .env variables connectGenAI reads for the tutor's calls (see missingAISettings).
TUTOR_SETTINGS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TOP_P",
    "LLM_MAX_TOKENS",
)

TRANSLATION_SYSTEM_MESSAGE = (
    "You are an English-Chinese dictionary for Hong Kong secondary school students. "
    "Translate the English word into Traditional Chinese, using the meaning given. "
    "Reply with only the Chinese translation (a few words at most), "
    "with no pinyin, no quotes and no explanation."
)

BATCH_TRANSLATION_SYSTEM_MESSAGE = (
    "You are an English-Chinese dictionary for Hong Kong secondary school students. "
    "The user gives a numbered list of English words, each with the meaning to use. "
    "Translate every word into Traditional Chinese. "
    "Reply with one line per word, in the same order, in the form "
    '"<number>. <Chinese translation>" (a few words at most), '
    "with no pinyin, no quotes and no explanation."
)

SENTENCE_SYSTEM_MESSAGE = (
    "You are a friendly English teacher for secondary school students. "
    "The student writes one sentence using a target word. "
    "Decide whether the target word is used with the right meaning "
    "and correct grammar. "
    "Reply in exactly this format:\n"
    "VERDICT: CORRECT or INCORRECT\n"
    "FEEDBACK: one or two short sentences in simple English. "
    "If the sentence is incorrect, include a corrected version."
)

VOCABULARY_SYSTEM_MESSAGE = (
    "You help Hong Kong secondary school students learn English vocabulary. "
    "From the text the user gives you, pick the most useful words or short phrases "
    "for a student to learn: "
    "words that are not too basic, appear in the text, and are worth remembering. "
    "Skip names of people and places. "
    "Reply with one word or phrase per line, in the form used in the text, "
    "with no numbers and no explanation."
)

# <think>...</think> blocks that some reasoning models put before their answer.
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)
# A label that the model sometimes writes before its translation, which is removed:
# "Translation", "Chinese", 中文 ("Chinese") or 翻譯 ("translation"), followed by an
# English colon ":" or the full-width colon "：" used in Chinese text.
TRANSLATION_LABEL = re.compile(
    r"^(translation|chinese|中文|翻譯)\s*[:：]\s*", re.IGNORECASE
)
# [\s*:]* also accepts Markdown bold, e.g. "**VERDICT:** CORRECT"
VERDICT = re.compile(r"VERDICT[\s*:]*(INCORRECT|CORRECT)", re.IGNORECASE)
FEEDBACK = re.compile(r"FEEDBACK[\s*:]*(.*)", re.IGNORECASE | re.DOTALL)
VERDICT_LINE = re.compile(r".*VERDICT.*", re.IGNORECASE)
# "1. word", "2) word", "- word", "* word", "• word"
LIST_MARKER = re.compile(r"^\s*(\d+\s*[.)]|[-*•])\s*")
# One line of a batch translation reply: "3. 挫折", "3) 挫折", "3: 挫折" or "3、挫折"
# (、 is the Chinese list comma). Markdown bold around the number is allowed.
NUMBERED_LINE = re.compile(r"^[\s*]*(\d+)[\s*]*[.)、:：][\s*]*(.*)$")
# The start of an explanation after the word, which is cut off: "word - meaning",
# "word: meaning", "word (n.)", or "word：meaning" with the full-width colon "：" used
# in Chinese text.
EXPLANATION = re.compile(r"\s+[-–—:]\s+|[(:：]")


def missingAISettings() -> list[str]:
    """
    List the .env variables the AI tutor still needs. connectGenAI has no defaults,
    and the tutor passes only its own system message and temperature, so every
    setting in TUTOR_SETTINGS must be filled in.

    Returns:
        list[str]: The missing or blank variables, in TUTOR_SETTINGS order. Empty
        when the tutor is ready.
    """

    return [name for name in TUTOR_SETTINGS if os.environ.get(name, "").strip() == ""]


def isAIAvailable() -> bool:
    """
    Return True when every setting in TUTOR_SETTINGS is set, so translation and
    sentence feedback can be used.
    """

    return not missingAISettings()


def stripThinking(text: str) -> str:
    """
    Remove <think>...</think> blocks that some reasoning models put before their answer.

    Parameters:
        Mandatory:
            - text (str): The model's reply.
    Returns:
        str: The reply without any <think>...</think> block (also one that spans
        several lines), and without spaces or empty lines at the start and end.
    """

    return THINKING.sub("", text).strip()


def cleanTranslation(reply: str) -> str:
    """
    Turn the model's reply into a short translation:
    keep the first non-empty line, drop labels like "Translation:" and surrounding
    quotes.
    Example: '<think>...</think>\\nTranslation: 「貓」。' -> "貓" (Chinese for "cat")

    Parameters:
        Mandatory:
            - reply (str): The model's reply to the translation request.
    Returns:
        str: The translation, at most MAX_TRANSLATION_LENGTH (40) characters, or "" if
        the reply has no text.
    """

    lines = [eachLine.strip() for eachLine in stripThinking(reply).splitlines()]
    firstLine = next((eachLine for eachLine in lines if eachLine), "")

    firstLine = TRANSLATION_LABEL.sub("", firstLine)
    # Remove the quotes and the full stop around the translation, English and Chinese:
    # 「」 and 『』 are Chinese quotation marks, “” are curly quotes, and 。 is the Chinese
    # full stop.
    firstLine = firstLine.strip(" \"'「」『』“”。.")

    return firstLine[:MAX_TRANSLATION_LENGTH]


def loadTranslationCache(cachePath: str) -> dict:
    """
    Load the saved translations, so a word that was translated before is not sent to
    the API again.

    Parameters:
        Mandatory:
            - cachePath (str): The cache file, e.g. "translation_cache/zh-TW.json".
    Returns:
        dict: {word in lowercase: translation}. An empty dict when the file is missing,
        cannot be read, is not valid JSON, or does not hold a JSON object.
    """

    if not os.path.exists(cachePath):
        return {}

    try:
        with open(cachePath, encoding="utf-8") as cacheFile:
            data = json.load(cacheFile)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def saveTranslationCache(cache: dict, cachePath: str) -> None:
    """
    Save the translations as indented JSON, with Chinese kept readable (not as \\u
    escapes). The folder is created when it does not exist.

    Parameters:
        Mandatory:
            - cache (dict): {word in lowercase: translation}, all translations to keep.
            - cachePath (str): The cache file. It is replaced.
    Raises:
        OSError: When the file cannot be written.
    """

    folder = os.path.dirname(cachePath)
    if folder != "":
        os.makedirs(folder, exist_ok=True)

    with open(cachePath, "w", encoding="utf-8") as cacheFile:
        cacheFile.write(json.dumps(cache, ensure_ascii=False, indent=2))


def translateWord(
    word: str,
    definition: str = "",
    cacheDir: str = TRANSLATION_CACHE_DIR,
    cacheFile: str = TRANSLATION_CACHE_FILE,
) -> str:
    """
    Translate an English word into Traditional Chinese with the LLM.
    Translations are saved in translation_cache/zh-TW.json, so each word is only sent to
    the API once.
    Parameters:
        Mandatory:
            - word (str): The English word.
        Optional:
            - definition (str): The English definition, so the right meaning is
              translated.
            - cacheDir (str): Folder for the translation cache.
            - cacheFile (str): File name of the translation cache.
    Returns:
        str: The translation, or "" if the model gave no answer.
    """

    cachePath = os.path.join(cacheDir, cacheFile)
    cache = loadTranslationCache(cachePath)
    key = word.strip().lower()

    if key in cache:
        return cache[key]

    reply = connectGenAI(
        f"Word: {word}\nMeaning: {definition}",
        systemMessage=TRANSLATION_SYSTEM_MESSAGE,
        temperature=0.2,
    )
    translation = cleanTranslation(reply)

    if translation != "":
        cache[key] = translation
        saveTranslationCache(cache, cachePath)

    return translation


def parseBatchTranslations(reply: str, words: list[str]) -> dict[str, str]:
    """
    Read the numbered translations from the model's reply to a batch request.
    Example: "1. 挫折\\n2. setbacks: 減少" with words ["setbacks", "diminish"] ->
    {"setbacks": "挫折", "diminish": "減少"}. The numbers decide which word a line
    belongs to, and an English word the model repeats before its translation is
    dropped.

    Parameters:
        Mandatory:
            - reply (str): The model's reply, one "<number>. <translation>" line per
              word.
            - words (list[str]): The words that were sent, in order (number 1 is
              words[0]).
    Returns:
        dict[str, str]: {word in lowercase: translation}. A word whose line is missing
        or empty is left out; a number outside the list is ignored.
    """

    translations = {}

    for eachLine in stripThinking(reply).splitlines():
        match = NUMBERED_LINE.match(eachLine)
        if match is None:
            continue

        index = int(match.group(1)) - 1
        if not 0 <= index < len(words):
            continue

        word = words[index]
        text = match.group(2).strip(" *")
        # "setbacks: 挫折" or "setbacks - 挫折" -> "挫折"
        text = re.sub(
            rf"^{re.escape(word)}\s*[-–—:：=]\s*", "", text, flags=re.IGNORECASE
        )
        translation = cleanTranslation(text)

        if translation != "":
            translations.setdefault(word.strip().lower(), translation)

    return translations


def translateBatch(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """
    Translate a few words with a single LLM request (see translateWords).

    Parameters:
        Mandatory:
            - pairs (list[tuple[str, str]]): (word, definition) for each word.
    Returns:
        dict[str, str]: {word in lowercase: translation}, see parseBatchTranslations.
        Empty when the request fails, so the other batches still count.
    """

    request = "\n".join(
        f"{number}. {word} (meaning: {definition or 'any'})"
        for number, (word, definition) in enumerate(pairs, start=1)
    )

    try:
        reply = connectGenAI(
            request, systemMessage=BATCH_TRANSLATION_SYSTEM_MESSAGE, temperature=0.2
        )
    except Exception:
        return {}

    return parseBatchTranslations(reply, [word for word, _ in pairs])


def translateWords(
    pairs: list[tuple[str, str]],
    cacheDir: str = TRANSLATION_CACHE_DIR,
    cacheFile: str = TRANSLATION_CACHE_FILE,
) -> dict[str, str]:
    """
    Translate many English words into Traditional Chinese at once.
    Words already in the translation cache are not sent again. The others go to the
    LLM TRANSLATION_BATCH_SIZE (20) at a time, in one request per batch, and up to
    MAX_TRANSLATION_REQUESTS (4) requests run at the same time. Importing 20 words
    therefore takes about as long as translating one word with translateWord.

    Parameters:
        Mandatory:
            - pairs (list[tuple[str, str]]): (word, English definition) for each word.
              The definition makes sure the right meaning is translated; it can be "".
        Optional:
            - cacheDir (str): Folder for the translation cache.
            - cacheFile (str): File name of the translation cache.
    Returns:
        dict[str, str]: {word in lowercase: translation}. A word the model did not
        translate, or whose batch failed (e.g. no internet), is left out.
    """

    cachePath = os.path.join(cacheDir, cacheFile)
    cache = loadTranslationCache(cachePath)

    translations = {}
    missing = []
    seen = set()

    for word, definition in pairs:
        key = word.strip().lower()
        if key in cache:
            translations[key] = cache[key]
        elif key not in seen:
            seen.add(key)
            missing.append((word, definition))

    if not missing:
        return translations

    batches = [
        missing[start : start + TRANSLATION_BATCH_SIZE]
        for start in range(0, len(missing), TRANSLATION_BATCH_SIZE)
    ]

    with ThreadPoolExecutor(
        max_workers=min(MAX_TRANSLATION_REQUESTS, len(batches))
    ) as pool:
        results = list(pool.map(translateBatch, batches))

    newTranslations = {}
    for eachResult in results:
        newTranslations.update(eachResult)

    if newTranslations:
        translations.update(newTranslations)
        cache.update(newTranslations)
        try:
            saveTranslationCache(cache, cachePath)
        except OSError:
            # The translations still go on the cards; they are just asked for again
            # next time.
            pass

    return translations


def parseSentenceFeedback(reply: str) -> tuple[bool | None, str]:
    """
    Read the VERDICT and FEEDBACK lines from the model's reply.
    Upper / lower case and Markdown bold ("**VERDICT:** CORRECT") do not matter.

    Parameters:
        Mandatory:
            - reply (str): The model's reply to the sentence check.
    Returns:
        tuple[bool | None, str]: (isCorrect, feedback).
            - isCorrect: True for CORRECT, False for INCORRECT, None if the reply has
              no verdict.
            - feedback: Everything after "FEEDBACK"; without a FEEDBACK label, the
              reply without its VERDICT line. Can be "".
    """

    text = stripThinking(reply)

    verdict = VERDICT.search(text)
    isCorrect = None if verdict is None else verdict.group(1).upper() == "CORRECT"

    feedback = FEEDBACK.search(text)
    if feedback is not None:
        return isCorrect, feedback.group(1).strip()

    return isCorrect, VERDICT_LINE.sub("", text).strip()


def parseVocabularyReply(
    reply: str, text: str, maxWords: int = DEFAULT_VOCABULARY_COUNT
) -> list[str]:
    """
    Read one word per line from the model's reply.
    Numbers, bullets and explanations after a dash are removed, and only words that
    really appear in the text are kept, so the model cannot invent words.

    Parameters:
        Mandatory:
            - reply (str): The model's reply, one word or phrase per line.
            - text (str): The passage the words were picked from.
        Optional:
            - maxWords (int): The most words to return.
              Default: DEFAULT_VOCABULARY_COUNT (20).
    Returns:
        list[str]: The words in the order the model gave them, each once (ignoring
        upper / lower case). A line longer than 3 words, or a word that is not in the
        text, is skipped.
    """

    loweredText = text.lower()
    words = []
    seen = set()

    for eachLine in stripThinking(reply).splitlines():
        word = EXPLANATION.split(LIST_MARKER.sub("", eachLine), maxsplit=1)[0]
        word = word.strip(" *\"'`.,")
        lowered = word.lower()

        if word == "" or len(word.split()) > 3:
            continue

        if lowered not in loweredText or lowered in seen:
            continue

        seen.add(lowered)
        words.append(word)

        if len(words) >= maxWords:
            break

    return words


def pickVocabulary(text: str, maxWords: int = DEFAULT_VOCABULARY_COUNT) -> list[str]:
    """
    Ask the LLM to pick the most useful words to learn from a passage.
    Only the first MAX_TEXT_FOR_AI characters are sent, to keep the request small.

    Parameters:
        Mandatory:
            - text (str): The passage, e.g. the text of an imported file.
        Optional:
            - maxWords (int): The most words to ask for and to return.
              Default: DEFAULT_VOCABULARY_COUNT (20).
    Returns:
        list[str]: The picked words that really appear in the text (see
        parseVocabularyReply). Can be empty.
    Raises:
        Exception: Whatever goes wrong while calling the LLM, e.g. no LLM_API_KEY or
        no internet (see connectGenAI).
    """

    shortText = text[:MAX_TEXT_FOR_AI]
    reply = connectGenAI(
        f"Pick up to {maxWords} words.\n\nText:\n{shortText}",
        systemMessage=VOCABULARY_SYSTEM_MESSAGE,
        temperature=0.3,
    )

    return parseVocabularyReply(reply, shortText, maxWords)


def checkSentence(word: str, definition: str, sentence: str) -> tuple[bool | None, str]:
    """
    Ask the LLM whether the student used the word correctly in a sentence: with the
    right meaning and correct grammar.

    Parameters:
        Mandatory:
            - word (str): The target word.
            - definition (str): The meaning the word should have, or "".
            - sentence (str): The student's sentence.
    Returns:
        tuple[bool | None, str]: (isCorrect, feedback), see parseSentenceFeedback.
        isCorrect is None when the model's answer could not be read.
    Raises:
        Exception: Whatever goes wrong while calling the LLM, e.g. no LLM_API_KEY or
        no internet (see connectGenAI).
    """

    reply = connectGenAI(
        f"Target word: {word}\nMeaning: {definition}\nStudent sentence: {sentence}",
        systemMessage=SENTENCE_SYSTEM_MESSAGE,
        temperature=0.3,
    )

    return parseSentenceFeedback(reply)
