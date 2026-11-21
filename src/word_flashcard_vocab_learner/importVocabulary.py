import csv
import importlib.util
import io
import locale
import os
import re
import shutil

import requests

from word_flashcard_vocab_learner import cardDeck, connectFreeDictionaryAPI, genAITutor, terminalDisplay
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card
from word_flashcard_vocab_learner.userInput import ask, askYesNo, isQuit


TEXT_EXTENSIONS = [".txt", ".md", ".csv", ".tsv"]
CSV_DELIMITERS = {".csv": ",", ".tsv": "\t"}

# Column names that mean "this column holds the Chinese translation".
TRANSLATION_HEADERS = ["chinese", "translation", "translated", "中文", "解释", "解釋", "意思"]
WORD_HEADERS = ["word", "words", "english", "vocabulary", "单词", "單詞", "英文"]
PDF_EXTENSIONS = [".pdf"]
WORD_EXTENSIONS = [".docx"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"]

MAX_IMPORT_WORDS = 100
MIN_PASSAGE_WORD_LENGTH = 3    # "cat" and "dog" are vocabulary too; very common words are filtered by COMMON_WORDS
MIN_PAGE_TEXT_LENGTH = 3       # a page with less text than this is treated as a scanned page
WORD_LIST_SHARE = 0.7
OCR_DPI = 300
TESSERACT_ENV = "TESSERACT_CMD"
WINDOWS_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DOCUMENTS_EXTRA_HINT = 'pip install ".[documents]"'
OCR_EXTRA_HINT = 'pip install ".[ocr]" and install Tesseract OCR (https://github.com/tesseract-ocr/tesseract)'

ENGLISH_WORD = r"[A-Za-z]+(?:['’-][A-Za-z]+)*"

# A markdown/TOML front matter block at the start of a file: the "--- … ---" or "+++ … +++" header.
FRONT_MATTER = re.compile(r"\A\s*(?:-{3}|\+{3})[ \t]*\n.*?\n(?:-{3}|\+{3})[ \t]*\n", re.DOTALL)
# A link or an e-mail address. They are not vocabulary, and their parts must not be picked up as words.
URL_OR_EMAIL = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+\.[\w.]+")
# The label at the start of a note line ("Note: …", "- …"), which says nothing about the line being a list entry.
LINE_LABEL = re.compile(r"^\s*(?:[A-Za-z]{2,}\s*:|[-*•·▪◦]\s+)")
# The separator between the word and its meaning in a word list ("word - meaning", "word\tmeaning", "word 中文").
LIST_SEPARATOR = re.compile(r"\s+[-–—=]\s+|[\t,;]|[\u3000-\u9fff]")
SENTENCE_ENDINGS = (".", "!", "?")

# Very common English words. They are skipped when words are picked from a passage,
# because students usually already know them.
COMMON_WORDS = set("""
about above across actually after again against almost alone along already also although always among another
answer anyone anything anyway around asked away back became because become becomes been before began begin
behind being believe below best better between both bring brought build built call called came cannot careful
case cause certain change children city class close come comes coming could country course days decide
different does doing done door down during each early easy else end enough even ever every everyone everything example
eyes face fact family feel feet felt find fine first five food form found four free friend friends from full
gave getting girl give given gives giving goes going gone good great group grow half hand hands happen happy hard
have having head hear heard help here high himself home hope hour hours house however idea important inside
instead into itself just keep kind knew know known large last late later learn least leave left less life like
line list little live lives living long look looked looking lost made make makes making many mean means might mind
minute minutes more morning most mother move much must myself name near need needs never next nice night none
nothing number often once only open other others over page part people perhaps person picture place play
please point problem put question quite rather read ready real really right room said same school second seem
seemed seen sentence several shall short should show side since small some someone something sometimes soon
sound start started still stop story student students such sure take taken takes talk teacher team tell than thank
that their them then there these they thing things think this those though thought three through time times
today together told took toward towards tried true trying turn under until upon used using very want wanted
water week weeks well went were what when where whether which while white whole whose will with within without
word words work world would write writing written wrong year years young your yours yourself
""".split())

# Three-letter function words, which can now come out of a passage ("the cat sat on the mat").
# Only grammar words go here: "new", "day" or "see" are vocabulary a student may still want.
COMMON_WORDS.update("""
the and for you are but not all can her was one our out who get has had him his how its may now
off she too two use yes yet any own did let put say why ago nor per via far few lot
""".split())


HEADING_WORDS = set("""
word words vocabulary vocab english unit lesson chapter page list name class date topic part section
""".split())
COLUMN_TITLES = ["word", "words", "vocabulary", "vocab", "english", "term"]

# Endings removed to check whether a word is just a form of a common word ("showed" -> "show").
WORD_ENDINGS = ["ing", "ed", "es", "er", "est", "ly", "s", "d"]


def isCommonWord(word: str) -> bool:

    """
    Return True if the word, or the word without a simple ending, is a very common word.
    Examples: "showed" (show), "making" (make), "friends" (friend)
    """

    if word in COMMON_WORDS:
        return True

    for eachEnding in WORD_ENDINGS:
        if not word.endswith(eachEnding):
            continue

        stem = word[:-len(eachEnding)]
        if len(stem) < 3:
            continue

        if stem in COMMON_WORDS or stem + "e" in COMMON_WORDS:
            return True

        # "earlier" -> "earli" -> "early"
        if stem.endswith("i") and stem[:-1] + "y" in COMMON_WORDS:
            return True

        # A doubled last letter, e.g. "stopped" -> "stopp" -> "stop"
        if len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in COMMON_WORDS:
            return True

    return False


class FileImportError(Exception):

    """
    A problem that should be shown to the user as a simple message
    (unsupported file type, missing library, OCR not installed, ...).
    """


# ---------- Reading text from files ----------

def cleanPath(path: str) -> str:

    """
    Tidy a path the user typed or dragged into the terminal: remove surrounding quotes and expand "~".
    """

    path = path.strip().strip('"').strip("'")
    return os.path.expanduser(path)


def readTextFromFile(path: str) -> str:

    """
    Read all the text from a text, CSV, PDF, Word (.docx) or image file.
    Scanned PDFs and images are read with OCR (Tesseract).
    Raises FileImportError with a simple message if the file cannot be read.
    """

    if not os.path.isfile(path):
        raise FileImportError(f"File not found: {path}")

    extension = os.path.splitext(path)[1].lower()

    if extension in CSV_DELIMITERS:
        return readCSVFile(path, CSV_DELIMITERS[extension])

    if extension in TEXT_EXTENSIONS:
        return readTextFile(path)

    if extension in PDF_EXTENSIONS:
        return readPDF(path)

    if extension in WORD_EXTENSIONS:
        return readWordDocument(path)

    if extension in IMAGE_EXTENSIONS:
        return readImage(path)

    if extension == ".doc":
        raise FileImportError("Old Word .doc files are not supported. Open the file in Word and save it as .docx.")

    supported = TEXT_EXTENSIONS + PDF_EXTENSIONS + WORD_EXTENSIONS + IMAGE_EXTENSIONS
    raise FileImportError(f"Unsupported file type '{extension}'. Supported: {', '.join(supported)}")


def readTextFile(path: str) -> str:

    """
    Read a plain text file. Tries UTF-8 first, then the computer's own encoding (e.g. Big5 on a Hong Kong PC).
    """

    with open(path, "rb") as textFile:
        data = textFile.read()

    text = None
    for eachEncoding in ["utf-8-sig", locale.getpreferredencoding(False)]:
        try:
            text = data.decode(eachEncoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if text is None:
        text = data.decode("utf-8", errors="replace")

    # Windows files end lines with "\r\n"
    return text.replace("\r\n", "\n").replace("\r", "\n")


def readCSVFile(path: str, delimiter: str) -> str:

    """
    Read the first column of a CSV / TSV file (e.g. a deck exported from this app, Excel or Quizlet),
    one word per line. Cells may contain line breaks, so the csv module is used instead of reading lines.
    """

    text = readTextFile(path)
    words = []

    for eachRow in csv.reader(io.StringIO(text), delimiter=delimiter):
        if len(eachRow) > 0 and eachRow[0].strip() != "":
            words.append(eachRow[0].strip())

    return "\n".join(words)


def readCSVTranslations(path: str, delimiter: str) -> dict[str, str]:

    """
    Read the translation column of a CSV / TSV file, e.g. a deck exported from this app.
    Returns {word (casefolded): translation}; an empty dict if the file has no such column.
    The header row decides the columns, so column 1 is only assumed to be the word
    when the header does not say otherwise.
    """

    text = readTextFile(path)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))

    if len(rows) == 0:
        return {}

    header = [eachCell.strip().casefold() for eachCell in rows[0]]

    translationIndex = -1
    for index, eachHeader in enumerate(header):
        if eachHeader in TRANSLATION_HEADERS:
            translationIndex = index
            break

    if translationIndex == -1:
        return {}

    wordIndex = 0
    for index, eachHeader in enumerate(header):
        if eachHeader in WORD_HEADERS:
            wordIndex = index
            break

    translations = {}
    for eachRow in rows[1:]:
        if len(eachRow) <= max(wordIndex, translationIndex):
            continue

        word = eachRow[wordIndex].strip()
        translation = eachRow[translationIndex].strip()

        # The exported header row is not a word.
        if word == "" or translation == "" or word.casefold() == header[wordIndex]:
            continue

        translations[word.casefold()] = translation

    return translations


def readPDF(path: str) -> str:

    """
    Read the text of every page of a PDF.
    Pages without text (scanned pages) are read with OCR when it is installed.
    """

    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise FileImportError(f"Reading PDF files needs: {DOCUMENTS_EXTRA_HINT}") from error

    try:
        reader = PdfReader(path)

        if reader.is_encrypted:
            reader.decrypt("")

        pageTexts = []
        for eachPage in reader.pages:
            pageTexts.append(eachPage.extract_text() or "")

    except Exception as error:
        raise FileImportError(f"Could not read the PDF: {error}") from error

    scannedPages = []
    for index, eachText in enumerate(pageTexts):
        if len(eachText.strip()) < MIN_PAGE_TEXT_LENGTH:
            scannedPages.append(index)

    if len(scannedPages) > 0:
        if isOCRAvailable():
            images = renderPDFPages(path, scannedPages)
            for pageIndex, eachImage in zip(scannedPages, images):
                pageTexts[pageIndex] = runOCR(eachImage)

        elif len(scannedPages) == len(pageTexts):
            raise FileImportError(f"This PDF looks scanned (it has no text). Reading it needs OCR: {OCR_EXTRA_HINT}")

    return "\n".join(pageTexts)


def readWordDocument(path: str) -> str:

    """
    Read the paragraphs and table cells of a Word (.docx) document.
    """

    try:
        import docx
    except ImportError as error:
        raise FileImportError(f"Reading Word files needs: {DOCUMENTS_EXTRA_HINT}") from error

    try:
        document = docx.Document(path)
    except Exception as error:
        raise FileImportError(f"Could not read the Word document: {error}") from error

    lines = []

    for eachParagraph in document.paragraphs:
        lines.append(eachParagraph.text)

    for eachTable in document.tables:
        for eachRow in eachTable.rows:
            cells = []
            for eachCell in eachRow.cells:
                cells.append(eachCell.text.strip())
            lines.append("\t".join(cells))

    return "\n".join(lines)


def readImage(path: str) -> str:

    """
    Read the text in a photo or scan with OCR.
    """

    try:
        from PIL import Image
    except ImportError as error:
        raise FileImportError(f"Reading images needs: {OCR_EXTRA_HINT}") from error

    try:
        image = Image.open(path)
    except Exception as error:
        raise FileImportError(f"Could not open the image: {error}") from error

    return runOCR(image)


def findTesseract() -> str | None:

    """
    Find the Tesseract program: the TESSERACT_CMD setting, then PATH, then the usual Windows install folder.
    """

    customPath = os.environ.get(TESSERACT_ENV)
    if customPath and os.path.isfile(customPath):
        return customPath

    pathOnSystem = shutil.which("tesseract")
    if pathOnSystem is not None:
        return pathOnSystem

    if os.name == "nt" and os.path.isfile(WINDOWS_TESSERACT_PATH):
        return WINDOWS_TESSERACT_PATH

    return None


def isOCRAvailable() -> bool:

    """
    Return True when pytesseract, Pillow and the Tesseract program are all installed.
    """

    for eachModule in ["pytesseract", "PIL"]:
        if importlib.util.find_spec(eachModule) is None:
            return False

    return findTesseract() is not None


def runOCR(image) -> str:

    """
    Read English text from a Pillow image with Tesseract.
    """

    try:
        import pytesseract
    except ImportError as error:
        raise FileImportError(f"Reading scans needs OCR: {OCR_EXTRA_HINT}") from error

    tesseractPath = findTesseract()
    if tesseractPath is None:
        raise FileImportError(
            "Tesseract OCR is not installed or not found. Install it, "
            f"or set {TESSERACT_ENV} in .env to the full path of tesseract.exe."
        )

    pytesseract.pytesseract.tesseract_cmd = tesseractPath

    try:
        return pytesseract.image_to_string(image, lang="eng")
    except Exception as error:
        raise FileImportError(f"OCR failed: {error}") from error


def renderPDFPages(path: str, pageIndexes: list[int]) -> list:

    """
    Turn PDF pages into Pillow images so they can be read with OCR.
    """

    try:
        import pypdfium2
    except ImportError as error:
        raise FileImportError(f"Reading scanned PDFs needs: {OCR_EXTRA_HINT}") from error

    pdf = pypdfium2.PdfDocument(path)
    images = []

    try:
        for eachIndex in pageIndexes:
            bitmap = pdf[eachIndex].render(scale=OCR_DPI / 72)
            images.append(bitmap.to_pil())
    finally:
        pdf.close()

    return images


# ---------- Finding vocabulary in the text ----------

def cleanText(text: str) -> str:

    """
    Remove the parts of a file that are not vocabulary: a byte order mark, a markdown front matter
    block at the top, and links or e-mail addresses. Otherwise "---", "title: test" and the parts of a
    URL make the text look like a word list and end up as cards.
    """

    text = text.replace("\ufeff", "")
    text = FRONT_MATTER.sub("", text, count=1)
    return URL_OR_EMAIL.sub(" ", text)


def isSentenceLine(line: str) -> bool:

    """
    Return True for a line of prose (a sentence), which a word list never contains.
    Such a line ends with . ! ? and is not "word - meaning" with a list separator in it.
    """

    stripped = line.strip()

    if not stripped.endswith(SENTENCE_ENDINGS):
        return False

    body = LINE_LABEL.sub("", stripped)

    if LIST_SEPARATOR.search(body):
        return False

    return len(body.split()) >= 2


def lineHead(line: str) -> str:

    """
    The part of a word-list line before its meaning.
    Examples: "1. ambiguous - unclear" -> "ambiguous", "ice cream (n.) 雪糕" -> "ice cream"
    """

    line = re.sub(r"^\s*(\d+\s*[.)、]|[-*•·▪◦])\s*", "", line)
    head = re.split(r"\s+[-–—=:]\s*|[\t,;:：(（\[=]|[\u3000-\u9fff]", line, maxsplit=1)[0]

    return head.strip()


def wordFromListLine(line: str) -> str | None:

    """
    Return the English word or short phrase (up to 3 words) at the start of a word-list line,
    or None if the line does not start with an English word.
    """

    head = lineHead(line)

    if re.fullmatch(ENGLISH_WORD + r"(?: " + ENGLISH_WORD + r"){0,2}", head):
        return head.replace("’", "'")

    firstWord = re.match(ENGLISH_WORD, head)
    if firstWord is not None:
        return firstWord.group(0).replace("’", "'")

    return None


def looksLikeWordList(text: str) -> bool:

    """
    Return True if most lines are short (a word list), False if the text is a passage of sentences.
    A line of prose is never counted as short, even when it starts with "Note:" or contains a link.
    """

    lines = []
    for eachLine in text.splitlines():
        if eachLine.strip() != "":
            lines.append(eachLine)

    if len(lines) == 0:
        return False

    shortLines = 0
    for eachLine in lines:
        if isSentenceLine(eachLine):
            continue
        if len(lineHead(eachLine).split()) <= 3:
            shortLines += 1

    return shortLines / len(lines) >= WORD_LIST_SHARE


def isHeadingLine(line: str) -> bool:

    """
    Return True for title lines in a word list, e.g. "Unit 3 vocabulary", "Lesson 5", "Word" (a CSV header).
    """

    head = lineHead(line)

    if re.search(r"\d", head):
        return True

    words = head.lower().split()

    if len(words) == 0:
        return False

    # A single word is only a heading if it is a column title like "Word"; "unit" on its own is vocabulary.
    if len(words) == 1:
        return words[0] in COLUMN_TITLES

    return words[0] in HEADING_WORDS


def wordsFromList(text: str) -> list[str]:

    """
    Take the word at the start of every line, e.g. from a vocabulary list or a CSV file.
    Title lines such as "Unit 3 vocabulary" or a "Word" header are skipped.
    """

    words = []

    for eachLine in text.splitlines():
        # A line with a link or an e-mail in it is prose, not a vocabulary entry.
        if "://" in eachLine or "@" in eachLine:
            continue

        if isHeadingLine(eachLine):
            continue

        word = wordFromListLine(eachLine)
        if word is not None:
            words.append(word)

    return words


def wordsFromPassage(text: str) -> list[str]:

    """
    Pick possible vocabulary from a passage: skip short and very common words,
    and words that only appear with a capital letter (usually names), in order of first appearance.
    """

    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # join words split at the end of a line: "vocab-\nulary"

    order = []
    seenInLowercase = {}
    seenCapitalizedMidSentence = {}

    for eachMatch in re.finditer(ENGLISH_WORD, text):
        # "Note:" / "Example:" at the start of a line is a label, not vocabulary.
        if text[eachMatch.end():eachMatch.end() + 1] == ":":
            continue

        rawToken = eachMatch.group(0).replace("’", "'")
        token = re.split(r"[']", rawToken)[0]   # "student's" -> "student"

        # "isn't" -> "is", "don't" -> "do" (never "isn" or "don").
        if rawToken.lower().endswith("n't"):
            token = re.sub(r"[nN]'t$", "", rawToken)
            token = {"ca": "can", "wo": "will", "sha": "shall"}.get(token.lower(), token)

        lowered = token.lower()

        if len(lowered) < MIN_PASSAGE_WORD_LENGTH or isCommonWord(lowered):
            continue

        if lowered not in seenInLowercase:
            order.append(lowered)
            seenInLowercase[lowered] = False
            seenCapitalizedMidSentence[lowered] = False

        if not token[0].isupper():
            seenInLowercase[lowered] = True
        elif not isSentenceStart(text, eachMatch.start()):
            seenCapitalizedMidSentence[lowered] = True

    # A word written with a capital letter in the middle of a sentence, and never in lowercase, is usually a name.
    words = []
    for eachWord in order:
        if seenInLowercase[eachWord] or not seenCapitalizedMidSentence[eachWord]:
            words.append(eachWord)

    return removePlurals(words)


def isSentenceStart(text: str, position: int) -> bool:

    """
    Return True if the word at this position starts a sentence or a line (so its capital letter says nothing).
    """

    before = text[max(0, position - 6):position].rstrip(" \t\"'“‘(")

    if position == 0 or before == "":
        return True

    return before[-1] in ".!?:\n\r"


def removePlurals(words: list[str]) -> list[str]:

    """
    Drop simple plural forms when the singular is also in the list: "cats" (with "cat"), "boxes", "stories".
    """

    wordSet = set(words)
    result = []

    for eachWord in words:
        singulars = []
        if eachWord.endswith("ies"):
            singulars.append(eachWord[:-3] + "y")
        if eachWord.endswith("es"):
            singulars.append(eachWord[:-2])
        if eachWord.endswith("s"):
            singulars.append(eachWord[:-1])

        isPlural = False
        for eachSingular in singulars:
            if eachSingular in wordSet:
                isPlural = True

        if not isPlural:
            result.append(eachWord)

    return result


def extractWords(text: str) -> list[str]:

    """
    Find the vocabulary in some text: a word list gives one word per line,
    a passage gives its less common words. Duplicates are removed (ignoring case), order is kept.
    """

    text = cleanText(text)

    if looksLikeWordList(text):
        candidates = wordsFromList(text)
    else:
        candidates = wordsFromPassage(text)

    return uniqueWords(candidates)


def uniqueWords(words: list[str]) -> list[str]:

    seen = set()
    result = []

    for eachWord in words:
        key = eachWord.casefold()
        if key not in seen:
            seen.add(key)
            result.append(eachWord)

    return result


def removeKnownWords(words: list[str], cards: list[Card]) -> list[str]:

    """
    Remove the words that are already in the deck.
    """

    result = []
    for eachWord in words:
        if cardDeck.findCard(cards, eachWord) is None:
            result.append(eachWord)

    return result


# ---------- Choosing words ----------

def parseSelection(answer: str, count: int) -> list[int] | None:

    """
    Turn the user's choice into item indexes (starting from 0).
    Accepts "" or "all" (everything), "n" / "none" (nothing), and numbers or ranges like "1,3,5-8".
    Returns None if the answer is not valid.
    """

    answer = answer.strip().lower()

    if answer in ["", "a", "all"]:
        return list(range(count))

    if answer in ["n", "no", "none"]:
        return []

    indexes = []

    for eachPart in re.split(r"[,\s]+", answer):
        if eachPart == "":
            continue

        rangeMatch = re.fullmatch(r"(\d+)\s*-\s*(\d+)", eachPart)

        if rangeMatch is not None:
            start, end = int(rangeMatch.group(1)), int(rangeMatch.group(2))
            if start > end:
                start, end = end, start
            numbers = range(start, end + 1)
        elif eachPart.isdigit():
            numbers = [int(eachPart)]
        else:
            return None

        for eachNumber in numbers:
            if eachNumber < 1 or eachNumber > count:
                return None
            if eachNumber - 1 not in indexes:
                indexes.append(eachNumber - 1)

    return indexes


def askWhichWords(words: list[str]) -> list[str] | None:

    """
    Show the found words in numbered columns and let the user choose which ones to add.
    Returns None if the user wants to go back.
    """

    numberWidth = len(str(len(words)))
    items = []
    for index, eachWord in enumerate(words, start=1):
        shownWord = terminalDisplay.truncateText(eachWord, terminalDisplay.MAX_WORD_COLUMN_WIDTH)
        items.append(f"{index:>{numberWidth}}. {shownWord}")

    print(terminalDisplay.formatColumns(items))
    print()
    print(ChatColor.paint("Which words do you want to add?", ChatColor.BOLD))
    print(ChatColor.paint("  Enter = all,  e.g. 1,3,5-8 = some,  n = none", ChatColor.DARK_GRAY))

    while True:
        answer = ask("Your choice: ", ChatColor.YELLOW)

        if answer is None or answer.lower() in ["q", "quit", "exit"]:
            return None

        indexes = parseSelection(answer, len(words))

        if indexes is not None:
            selected = []
            for eachIndex in indexes:
                selected.append(words[eachIndex])
            return selected

        print(ChatColor.paint(f"Please type numbers from 1 to {len(words)}, e.g. 1,3,5-8.", ChatColor.ORANGE))


# ---------- Adding words to the deck ----------

def createCard(word: str) -> tuple[Card | None, str]:

    """
    Look up a word and turn it into a card (with a Chinese translation if the AI tutor is set up).
    Returns (card, "") or (None, reason it was skipped).
    """

    try:
        result = connectFreeDictionaryAPI.getWordDefinition(word)
    except requests.RequestException as error:
        return None, f"could not reach the dictionary ({error})"

    if len(result["definitions"]) == 0:
        return None, "not found in the dictionary"

    translation = ""
    if genAITutor.isAIAvailable():
        try:
            translation = genAITutor.translateWord(result["word"], result["definitions"][0])
        except Exception:
            translation = ""

    return Card.fromLookup(result, translation), ""


def addWords(words: list[str], cards: list[Card], deckPath: str, translations: dict[str, str] | None = None) -> dict:

    """
    Look up each word and add it to the deck, showing progress line by line.
    The deck is saved after every word, so nothing is lost if the user stops.
    Returns {"added": int, "skipped": int}.
    """

    summary = {"added": 0, "skipped": 0}
    wordWidth = max(len(eachWord) for eachWord in words)
    counterWidth = len(str(len(words)))

    for index, eachWord in enumerate(words, start=1):
        counter = ChatColor.paint(f"  [{index:>{counterWidth}}/{len(words)}] ", ChatColor.DARK_GRAY)
        start = counter + f"{eachWord:<{wordWidth}}  "

        card, reason = createCard(eachWord)

        if card is None:
            summary["skipped"] += 1
            print(start + ChatColor.paint(f"skipped: {reason}", ChatColor.ORANGE))
            continue

        # A translation column in the user's own CSV wins over the AI tutor.
        if translations is not None:
            translation = translations.get(card.word.casefold(), "")
            if translation != "":
                card.translation = translation

        if not cardDeck.addCard(cards, card):
            summary["skipped"] += 1
            print(start + ChatColor.paint(f'skipped: "{card.word}" is already in your deck', ChatColor.DARK_GRAY))
            continue

        try:
            cardDeck.saveDeck(cards, deckPath)
        except cardDeck.DeckSaveError as error:
            print(start + ChatColor.paint(f"skipped: {error}", ChatColor.RED))
            summary["skipped"] += 1
            cards.remove(card)
            break

        summary["added"] += 1

        addedText = ChatColor.paint("added", ChatColor.GREEN)
        if card.translation != "":
            addedText += ChatColor.paint(f"  {card.translation}", ChatColor.DARK_GRAY)
        print(start + addedText)

    return summary


# ---------- The whole import flow ----------

def chooseWordsWithAI(text: str, words: list[str]) -> list[str]:

    """
    If the AI tutor is set up and the text is a passage, offer to let it pick the most useful words.
    Falls back to the words found without AI if it fails.
    """

    if not genAITutor.isAIAvailable() or looksLikeWordList(text):
        return words

    if not askYesNo("Let the AI tutor pick the most useful words? (Y/n) ", default=True):
        return words

    print(ChatColor.paint("Asking the AI tutor...", ChatColor.BLUE))

    try:
        picked = genAITutor.pickVocabulary(text)
    except Exception as error:
        print(ChatColor.paint(f"Could not reach the AI tutor: {error}", ChatColor.ORANGE))
        return words

    if len(picked) == 0:
        print(ChatColor.paint("The AI tutor did not pick any words, so all found words are shown.", ChatColor.ORANGE))
        return words

    return picked


def importVocabulary(cards: list[Card], deckPath: str) -> None:

    """
    Ask for a file, find the vocabulary in it, let the user choose words, and add them to the deck.
    """

    print(ChatColor.paint("Import words from a text, CSV, PDF, Word (.docx) or image file.", ChatColor.DARK_GRAY))
    print(ChatColor.paint("Tip: you can drag the file into this window to type its path.", ChatColor.DARK_GRAY))
    print()

    answer = ask("File path (Enter = back): ", ChatColor.BOLD, ChatColor.YELLOW)
    if isQuit(answer) or answer == "":
        return

    path = cleanPath(answer)
    print(ChatColor.paint("Reading the file...", ChatColor.BLUE))

    try:
        text = readTextFromFile(path)
    except FileImportError as error:
        print(ChatColor.paint(str(error), ChatColor.RED))
        return

    translations = {}
    extension = os.path.splitext(path)[1].lower()
    if extension in CSV_DELIMITERS:
        translations = readCSVTranslations(path, CSV_DELIMITERS[extension])

    words = extractWords(text)
    words = chooseWordsWithAI(text, words)

    foundCount = len(words)
    words = removeKnownWords(words, cards)
    knownCount = foundCount - len(words)

    if len(words) == 0:
        if knownCount > 0:
            print(ChatColor.paint(f"All {knownCount} words in this file are already in your deck.", ChatColor.GREEN))
        else:
            print(ChatColor.paint("No English words were found in this file.", ChatColor.ORANGE))
        return

    tooManyCount = max(0, len(words) - MAX_IMPORT_WORDS)
    words = words[:MAX_IMPORT_WORDS]

    terminalDisplay.printHeading(f"Words found in {os.path.basename(path)}")

    notes = []
    if knownCount > 0:
        notes.append(f"{knownCount} already in your deck are hidden")
    if tooManyCount > 0:
        notes.append(f"only the first {MAX_IMPORT_WORDS} are shown")
    if len(notes) > 0:
        print(ChatColor.paint("  (" + "; ".join(notes) + ")", ChatColor.DARK_GRAY))
        print()

    selectedWords = askWhichWords(words)
    if selectedWords is None or len(selectedWords) == 0:
        print(ChatColor.paint("No words added.", ChatColor.DARK_GRAY))
        return

    terminalDisplay.printHeading(f"Adding {len(selectedWords)} words")

    summary = addWords(selectedWords, cards, deckPath, translations)

    print()
    print(ChatColor.paint(f"Added {summary['added']}, skipped {summary['skipped']}.", ChatColor.BOLD, ChatColor.GREEN))
