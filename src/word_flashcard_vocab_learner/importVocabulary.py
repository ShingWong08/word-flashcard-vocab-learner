import csv
import importlib.util
import io
import locale
import os
import re
import shutil

import requests

from word_flashcard_vocab_learner import (
    cardDeck,
    connectFreeDictionaryAPI,
    genAITutor,
    terminalDisplay,
)
from word_flashcard_vocab_learner.chatColor import ChatColor
from word_flashcard_vocab_learner.flashCard import Card
from word_flashcard_vocab_learner.userInput import ask, askYesNo, isQuit

TEXT_EXTENSIONS = [".txt", ".md", ".csv", ".tsv"]
CSV_DELIMITERS = {".csv": ",", ".tsv": "\t"}
PDF_EXTENSIONS = [".pdf"]
WORD_EXTENSIONS = [".docx"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"]

# Column titles of a CSV file that mean "this column holds the Chinese translation"
# (compared ignoring upper / lower case): the English titles, plus 中文 ("Chinese"),
# 解释 and 解釋 ("explanation", in simplified and in traditional characters) and 意思
# ("meaning").
TRANSLATION_HEADERS = [
    "chinese",
    "translation",
    "translated",
    "中文",
    "解释",
    "解釋",
    "意思",
]
# Column titles that mean "this column holds the English word": the English titles,
# plus 单词 and 單詞 ("word", in simplified and in traditional characters) and 英文
# ("English").
WORD_HEADERS = ["word", "words", "english", "vocabulary", "单词", "單詞", "英文"]

MAX_IMPORT_WORDS = 100
# "cat" and "dog" are vocabulary too; very common words are filtered by COMMON_WORDS.
MIN_PASSAGE_WORD_LENGTH = 3
# A page with less text than this is treated as a scanned page.
MIN_PAGE_TEXT_LENGTH = 3
WORD_LIST_SHARE = 0.7
OCR_DPI = 300
TESSERACT_ENV = "TESSERACT_CMD"
WINDOWS_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DOCUMENTS_EXTRA_HINT = 'pip install ".[documents]"'
OCR_EXTRA_HINT = (
    'pip install ".[ocr]" and install Tesseract OCR '
    "(https://github.com/tesseract-ocr/tesseract)"
)

ENGLISH_WORD = r"[A-Za-z]+(?:['’-][A-Za-z]+)*"
WORD = re.compile(ENGLISH_WORD)
# A word or a short phrase of up to 3 words.
PHRASE = re.compile(ENGLISH_WORD + r"(?: " + ENGLISH_WORD + r"){0,2}")

# A markdown/TOML front matter block at the start of a file:
# the "--- … ---" or "+++ … +++" header.
FRONT_MATTER = re.compile(
    r"\A\s*(?:-{3}|\+{3})[ \t]*\n.*?\n(?:-{3}|\+{3})[ \t]*\n", re.DOTALL
)
# A link or an e-mail address. They are not vocabulary, and their parts must not be
# picked up as words.
URL_OR_EMAIL = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+\.[\w.]+")
# The label at the start of a note line ("Note: …", "- …"), which says nothing about the
# line being a list entry.
LINE_LABEL = re.compile(r"^\s*(?:[A-Za-z]{2,}\s*:|[-*•·▪◦]\s+)")
# The separator between the word and its meaning in a word list: a dash or "=" with
# spaces around it, a tab, a comma, a semicolon, or the first Chinese character.
# Examples: "word - meaning", "word\tmeaning", "word 中文" (中文 stands for a meaning
# written in Chinese).
LIST_SEPARATOR = re.compile(r"\s+[-–—=]\s+|[\t,;]|[\u3000-\u9fff]")
# The number or bullet at the start of a word-list line: "1. ", "2) ", "3、", "- ", "• ".
# 、 is the comma that Chinese text uses after a list number.
LIST_MARKER = re.compile(r"^\s*(\d+\s*[.)、]|[-*•·▪◦])\s*")
# Where the meaning starts after the word in a word-list line: a dash, "=" or ":" after
# a space; a tab, comma, semicolon, colon or "="; an opening bracket "(" or "["; the
# full-width colon "：" and bracket "（" used in Chinese text; or the first Chinese
# character.
MEANING_START = re.compile(r"\s+[-–—=:]\s*|[\t,;:：(（\[=]|[\u3000-\u9fff]")
# Chinese characters and full-width punctuation: a cell with these is a translation, not
# an English meaning.
CHINESE_TEXT = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]")
# A word split at the end of a line: "vocab-\nulary"
SPLIT_WORD = re.compile(r"(\w)-\s*\n\s*(\w)")
NOT_ENDING = re.compile(r"[nN]'t$")
DIGIT = re.compile(r"\d")
NUMBERS = re.compile(r"(\d+)\s*-\s*(\d+)")
SELECTION_SEPARATOR = re.compile(r"[,\s]+")
SENTENCE_ENDINGS = (".", "!", "?")

# "can't" -> "ca" -> "can", "won't" -> "wo" -> "will", "shan't" -> "sha" -> "shall"
CONTRACTION_STEMS = {"ca": "can", "wo": "will", "sha": "shall"}

# Very common English words. They are skipped when words are picked from a passage,
# because students usually already know them.
COMMON_WORDS = set("""
about above across actually after again against almost alone along already also although
always among another answer anyone anything anyway around asked away back became because
become becomes been before began begin behind being believe below best better between
both bring brought build built call called came cannot careful case cause certain change
children city class close come comes coming could country course days decide different
does doing done door down during each early easy else end enough even ever every
everyone everything example eyes face fact family feel feet felt find fine first five
food form found four free friend friends from full gave getting girl give given gives
giving goes going gone good great group grow half hand hands happen happy hard have
having head hear heard help here high himself home hope hour hours house however idea
important inside instead into itself just keep kind knew know known large last late
later learn least leave left less life like line list little live lives living long look
looked looking lost made make makes making many mean means might mind minute minutes
more morning most mother move much must myself name near need needs never next nice
night none nothing number often once only open other others over page part people
perhaps person picture place play please point problem put question quite rather read
ready real really right room said same school second seem seemed seen sentence several
shall short should show side since small some someone something sometimes soon sound
start started still stop story student students such sure take taken takes talk teacher
team tell than thank that their them then there these they thing things think this those
though thought three through time times today together told took toward towards tried
true trying turn under until upon used using very want wanted water week weeks well went
were what when where whether which while white whole whose will with within without word
words work world would write writing written wrong year years young your yours yourself
""".split())

# Three-letter function words, which can now come out of a passage
# ("the cat sat on the mat"). Only grammar words go here: "new", "day" or "see" are
# vocabulary a student may still want.
COMMON_WORDS.update("""
the and for you are but not all can her was one our out who get has had him his how its
may now off she too two use yes yet any own did let put say why ago nor per via far few
lot
""".split())

HEADING_WORDS = set("""
word words vocabulary vocab english unit lesson chapter page list name class date topic
part section
""".split())
COLUMN_TITLES = ["word", "words", "vocabulary", "vocab", "english", "term"]

# Endings removed to check whether a word is just a form of a common word:
# "showed" -> "show".
WORD_ENDINGS = ["ing", "ed", "es", "er", "est", "ly", "s", "d"]


def isCommonWord(word: str) -> bool:
    """
    Tell whether the word, or the word without a simple ending, is a very common word.
    Examples: "showed" (show), "making" (make), "friends" (friend), "earlier" (early),
    "stopped" (stop)

    Parameters:
        Mandatory:
            - word (str): The word in lowercase.
    Returns:
        bool: True if the word is in COMMON_WORDS, or becomes a common word when an
        ending from WORD_ENDINGS is taken off (also adding back an "e", changing "i"
        back to "y", or undoing a doubled last letter). Stems shorter than 3 letters
        are not checked. Otherwise False.
    """

    if word in COMMON_WORDS:
        return True

    for eachEnding in WORD_ENDINGS:
        if not word.endswith(eachEnding):
            continue

        stem = word[: -len(eachEnding)]
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
    Tidy a path the user typed or dragged into the terminal: remove surrounding quotes
    and expand "~".

    Parameters:
        Mandatory:
            - path (str): The path as typed, e.g. '"C:\\My Files\\words.txt"' (a
              terminal adds the quotes when a file is dragged in) or "~/words.txt".
    Returns:
        str: The path without spaces or quotes around it, with "~" replaced by the
        home folder.
    """

    return os.path.expanduser(path.strip().strip('"').strip("'"))


def readTextFromFile(path: str) -> str:
    """
    Read all the text from a text, CSV, PDF, Word (.docx) or image file.
    Scanned PDFs and images are read with OCR (Tesseract). The file extension decides
    how the file is read (upper / lower case does not matter).

    Parameters:
        Mandatory:
            - path (str): The file to read.
    Returns:
        str: The text of the file. For a CSV / TSV file, only its first column, one
        cell per line (see readCSVFile).
    Raises:
        FileImportError: With a simple message for the user when the file does not
        exist, has an unsupported type (including old .doc files), needs a library or
        program that is not installed, or cannot be read.
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
        raise FileImportError(
            "Old Word .doc files are not supported. "
            "Open the file in Word and save it as .docx."
        )

    supported = TEXT_EXTENSIONS + PDF_EXTENSIONS + WORD_EXTENSIONS + IMAGE_EXTENSIONS
    raise FileImportError(
        f"Unsupported file type '{extension}'. Supported: {', '.join(supported)}"
    )


def readTextFile(path: str) -> str:
    """
    Read a plain text file. Tries UTF-8 first, then the computer's own encoding (e.g.
    Big5 on a Hong Kong PC).

    Parameters:
        Mandatory:
            - path (str): The text file.
    Returns:
        str: The text, without a UTF-8 byte order mark, and with Windows ("\\r\\n") and
        old Mac ("\\r") line endings turned into "\\n". If neither encoding works, the
        file is read as UTF-8 with unreadable bytes replaced by "�".
    Raises:
        OSError: When the file cannot be opened.
    """

    with open(path, "rb") as textFile:
        data = textFile.read()

    for eachEncoding in ["utf-8-sig", locale.getpreferredencoding(False)]:
        try:
            text = data.decode(eachEncoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = data.decode("utf-8", errors="replace")

    # Windows files end lines with "\r\n"
    return text.replace("\r\n", "\n").replace("\r", "\n")


def readCSVRows(path: str, delimiter: str) -> list[list[str]]:
    """
    Read all rows of a CSV / TSV file. The text is read like any text file (see
    readTextFile), so both UTF-8 and the computer's own encoding work.

    Parameters:
        Mandatory:
            - path (str): The CSV or TSV file.
            - delimiter (str): The cell separator: "," for CSV, a tab for TSV.
    Returns:
        list[list[str]]: One list of cells for each row. Rows can have different
        lengths, and an empty line gives an empty list.
    """

    # Cells may contain line breaks, so the csv module is used instead of reading lines.
    return list(csv.reader(io.StringIO(readTextFile(path)), delimiter=delimiter))


def readCSVFile(path: str, delimiter: str) -> str:
    """
    Read the first column of a CSV / TSV file (e.g. a deck exported from this app, Excel
    or Quizlet), one word per line.

    Parameters:
        Mandatory:
            - path (str): The CSV or TSV file.
            - delimiter (str): The cell separator: "," for CSV, a tab for TSV.
    Returns:
        str: The first cell of every row, without spaces around it, joined with
        newlines. Empty cells and empty rows are left out. A header row such as "Word"
        is kept here; it is skipped later as a title line (see isHeadingLine).
    """

    cells = (eachRow[0].strip() for eachRow in readCSVRows(path, delimiter) if eachRow)
    return "\n".join(eachCell for eachCell in cells if eachCell != "")


def readCSVTranslations(path: str, delimiter: str) -> dict[str, str]:
    """
    Read the translation column of a CSV / TSV file, e.g. a deck exported from this app.
    The header row decides the columns, so column 1 is only assumed to be the word
    when the header does not say otherwise. A file without a header row still works
    when its second column holds Chinese (e.g. "cat,貓").

    Parameters:
        Mandatory:
            - path (str): The CSV or TSV file.
            - delimiter (str): The cell separator: "," for CSV, a tab for TSV.
    Returns:
        dict[str, str]: {word in lowercase (casefold): translation}. Rows that are too
        short, or have an empty word or translation, are skipped. An empty dict if the
        file has no translation column.
    """

    rows = readCSVRows(path, delimiter)

    if not rows:
        return {}

    header = [eachCell.strip().casefold() for eachCell in rows[0]]
    translationIndex = columnIndex(header, TRANSLATION_HEADERS, -1)
    hasHeader = translationIndex != -1

    if hasHeader:
        dataRows = rows[1:]
    elif any(len(eachRow) > 1 and CHINESE_TEXT.search(eachRow[1]) for eachRow in rows):
        # No header names the translation column, e.g. a file of lines like "cat,貓"
        # (貓 is Chinese for "cat") with no header row. A second column that holds
        # Chinese is still taken as the translation.
        translationIndex = 1
        dataRows = rows
    else:
        return {}

    wordIndex = columnIndex(header, WORD_HEADERS, 0)
    lastIndex = max(wordIndex, translationIndex)

    translations = {}
    for eachRow in dataRows:
        if len(eachRow) <= lastIndex:
            continue

        word = eachRow[wordIndex].strip()
        translation = eachRow[translationIndex].strip()

        if word == "" or translation == "":
            continue

        # The exported header row is not a word.
        if hasHeader and word.casefold() == header[wordIndex]:
            continue

        translations[word.casefold()] = translation

    return translations


def columnIndex(header: list[str], names: list[str], default: int) -> int:
    """
    Find a column by its title.

    Parameters:
        Mandatory:
            - header (list[str]): The cells of the header row, already in lowercase.
            - names (list[str]): The titles to look for, e.g. TRANSLATION_HEADERS.
            - default (int): What to return when no cell matches.
    Returns:
        int: The position (from 0) of the first header cell that is one of names, or
        default if there is none.
    """

    return next(
        (index for index, eachCell in enumerate(header) if eachCell in names), default
    )


def readPDF(path: str) -> str:
    """
    Read the text of every page of a PDF.
    Pages without text (scanned pages) are read with OCR when it is installed.
    A PDF that is locked with an empty password is opened too.

    Parameters:
        Mandatory:
            - path (str): The PDF file.
    Returns:
        str: The text of all pages, one page after another. Without OCR, a scanned page
        in an otherwise normal PDF stays (almost) empty.
    Raises:
        FileImportError: When pypdf is not installed, the PDF cannot be read, or every
        page is scanned and OCR is not installed.
    """

    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise FileImportError(
            f"Reading PDF files needs: {DOCUMENTS_EXTRA_HINT}"
        ) from error

    try:
        reader = PdfReader(path)

        if reader.is_encrypted:
            reader.decrypt("")

        pageTexts = [eachPage.extract_text() or "" for eachPage in reader.pages]

    except Exception as error:
        raise FileImportError(f"Could not read the PDF: {error}") from error

    scannedPages = [
        index
        for index, eachText in enumerate(pageTexts)
        if len(eachText.strip()) < MIN_PAGE_TEXT_LENGTH
    ]

    if scannedPages:
        if isOCRAvailable():
            images = renderPDFPages(path, scannedPages)
            for pageIndex, eachImage in zip(scannedPages, images):
                pageTexts[pageIndex] = runOCR(eachImage)

        elif len(scannedPages) == len(pageTexts):
            raise FileImportError(
                "This PDF looks scanned (it has no text). "
                f"Reading it needs OCR: {OCR_EXTRA_HINT}"
            )

    return "\n".join(pageTexts)


def readWordDocument(path: str) -> str:
    """
    Read the paragraphs and table cells of a Word (.docx) document.

    Parameters:
        Mandatory:
            - path (str): The .docx file.
    Returns:
        str: Every paragraph on its own line, then every table row on its own line
        with its cells separated by tabs (so "word<tab>meaning" tables read like a word
        list).
    Raises:
        FileImportError: When python-docx is not installed or the file cannot be read.
    """

    try:
        import docx
    except ImportError as error:
        raise FileImportError(
            f"Reading Word files needs: {DOCUMENTS_EXTRA_HINT}"
        ) from error

    try:
        document = docx.Document(path)
    except Exception as error:
        raise FileImportError(f"Could not read the Word document: {error}") from error

    lines = [eachParagraph.text for eachParagraph in document.paragraphs]
    lines += [
        "\t".join(eachCell.text.strip() for eachCell in eachRow.cells)
        for eachTable in document.tables
        for eachRow in eachTable.rows
    ]

    return "\n".join(lines)


def readImage(path: str) -> str:
    """
    Read the text in a photo or scan with OCR.

    Parameters:
        Mandatory:
            - path (str): The image file (.png, .jpg, .jpeg, .bmp, .gif, .tif, .tiff or
              .webp).
    Returns:
        str: The English text that Tesseract found in the image.
    Raises:
        FileImportError: When Pillow, pytesseract or Tesseract is not installed, the
        image cannot be opened, or OCR fails.
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
    Find the Tesseract program: the TESSERACT_CMD setting, then PATH, then the usual
    Windows install folder.
    """

    customPath = os.environ.get(TESSERACT_ENV)
    if customPath and os.path.isfile(customPath):
        return customPath

    foundPath = shutil.which("tesseract")
    if foundPath is not None:
        return foundPath

    if os.name == "nt" and os.path.isfile(WINDOWS_TESSERACT_PATH):
        return WINDOWS_TESSERACT_PATH

    return None


def isOCRAvailable() -> bool:
    """
    Return True when pytesseract, Pillow and the Tesseract program are all installed.
    """

    hasModules = all(
        importlib.util.find_spec(eachModule) is not None
        for eachModule in ["pytesseract", "PIL"]
    )
    return hasModules and findTesseract() is not None


def runOCR(image) -> str:
    """
    Read English text from a Pillow image with Tesseract.

    Parameters:
        Mandatory:
            - image (PIL.Image.Image): The picture to read, e.g. an opened photo or a
              rendered PDF page.
    Returns:
        str: The text that Tesseract found.
    Raises:
        FileImportError: When pytesseract is not installed, the Tesseract program
        cannot be found (see findTesseract), or OCR fails.
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
    The pages are rendered at OCR_DPI (300 dots per inch), sharp enough for OCR.

    Parameters:
        Mandatory:
            - path (str): The PDF file.
            - pageIndexes (list[int]): The pages to render, counted from 0.
    Returns:
        list: One Pillow image per page, in the same order as pageIndexes.
    Raises:
        FileImportError: When pypdfium2 is not installed.
    """

    try:
        import pypdfium2
    except ImportError as error:
        raise FileImportError(
            f"Reading scanned PDFs needs: {OCR_EXTRA_HINT}"
        ) from error

    pdf = pypdfium2.PdfDocument(path)

    try:
        return [
            pdf[eachIndex].render(scale=OCR_DPI / 72).to_pil()
            for eachIndex in pageIndexes
        ]
    finally:
        pdf.close()


# ---------- Finding vocabulary in the text ----------


def cleanText(text: str) -> str:
    """
    Remove the parts of a file that are not vocabulary: a byte order mark, a markdown
    front matter block at the top, and links or e-mail addresses. Otherwise "---",
    "title: test" and the parts of a URL make the text look like a word list and end up
    as cards.

    Parameters:
        Mandatory:
            - text (str): The text read from a file.
    Returns:
        str: The text without byte order marks, without a front matter block at the
        very start ("--- ... ---" or "+++ ... +++"), and with every link or e-mail
        address replaced by a space.
    """

    text = text.replace("\ufeff", "")
    text = FRONT_MATTER.sub("", text, count=1)
    return URL_OR_EMAIL.sub(" ", text)


def isSentenceLine(line: str) -> bool:
    """
    Tell whether a line is prose (a sentence), which a word list never contains.
    Such a line ends with . ! ? and is not "word - meaning" with a list separator in it.

    Parameters:
        Mandatory:
            - line (str): One line of the text.
    Returns:
        bool: True if the line ends with . ! or ?, has no list separator (see
        LIST_SEPARATOR) once a label like "Note:" or a bullet is removed, and has at
        least two words. Otherwise False.
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
    Examples:
        "1. ambiguous - unclear" -> "ambiguous"
        "ice cream (n.) 雪糕"    -> "ice cream"   (雪糕 is Chinese for "ice cream")

    Parameters:
        Mandatory:
            - line (str): One line of a word list.
    Returns:
        str: The line without its number or bullet (see LIST_MARKER), cut where the
        meaning starts (see MEANING_START), without spaces around it. Can be "".
    """

    return MEANING_START.split(LIST_MARKER.sub("", line), maxsplit=1)[0].strip()


def wordFromListLine(line: str) -> str | None:
    """
    Return the English word or short phrase (up to 3 words) at the start of a word-list
    line, or None if the line does not start with an English word.

    Parameters:
        Mandatory:
            - line (str): One line of a word list.
    Returns:
        str | None: The whole head of the line (see lineHead) when it is 1 to 3
        English words; otherwise just its first English word. Curly apostrophes become
        straight ones ("rock’n’roll" -> "rock'n'roll"). None when the head does not
        start with an English letter, e.g. a line that is only Chinese.
    """

    head = lineHead(line)

    if PHRASE.fullmatch(head):
        return head.replace("’", "'")

    firstWord = WORD.match(head)
    if firstWord is not None:
        return firstWord.group(0).replace("’", "'")

    return None


def looksLikeWordList(text: str) -> bool:
    """
    Tell whether the text is a word list (most lines are short) or a passage of
    sentences. A line of prose is never counted as short, even when it starts with
    "Note:" or contains a link.

    Parameters:
        Mandatory:
            - text (str): The whole text, already cleaned (see cleanText).
    Returns:
        bool: True if at least WORD_LIST_SHARE (70%) of the non-empty lines are short:
        not a sentence (see isSentenceLine) and at most 3 words before the meaning.
        False for a passage, and for a text without any lines.
    """

    lines = [eachLine for eachLine in text.splitlines() if eachLine.strip() != ""]

    if not lines:
        return False

    shortLines = sum(
        1
        for eachLine in lines
        if not isSentenceLine(eachLine) and len(lineHead(eachLine).split()) <= 3
    )

    return shortLines / len(lines) >= WORD_LIST_SHARE


def isHeadingLine(line: str) -> bool:
    """
    Tell whether a line is a title in a word list, e.g. "Unit 3 vocabulary",
    "Lesson 5", "Word" (a CSV header), so it is not taken as a word.

    Parameters:
        Mandatory:
            - line (str): One line of a word list.
    Returns:
        bool: True if the head of the line (see lineHead) contains a digit, is a single
        column title such as "Word" or "Vocabulary" (see COLUMN_TITLES), or has several
        words and starts with a heading word such as "unit", "lesson" or "list" (see
        HEADING_WORDS). Otherwise False.
    """

    head = lineHead(line)

    if DIGIT.search(head):
        return True

    words = head.lower().split()

    if not words:
        return False

    # A single word is only a heading if it is a column title like "Word"; "unit" on its
    # own is vocabulary.
    if len(words) == 1:
        return words[0] in COLUMN_TITLES

    return words[0] in HEADING_WORDS


def wordsFromList(text: str) -> list[str]:
    """
    Take the word at the start of every line, e.g. from a vocabulary list or a CSV file.
    Title lines such as "Unit 3 vocabulary" or a "Word" header are skipped.

    Parameters:
        Mandatory:
            - text (str): A word list, one entry per line.
    Returns:
        list[str]: The word or phrase of every line (see wordFromListLine), in order.
        Lines with a link or an e-mail address, title lines, and lines without an
        English word are skipped. Duplicates are still in the list.
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
    and words that only appear with a capital letter (usually names), in order of first
    appearance.

    Parameters:
        Mandatory:
            - text (str): The passage, already cleaned (see cleanText).
    Returns:
        list[str]: The words in lowercase, each once, in order of first appearance.
        A word broken over two lines with a hyphen is joined first. Left out are:
        words shorter than MIN_PASSAGE_WORD_LENGTH (3) letters, very common words and
        their forms (see isCommonWord), labels like "Note:", words only ever written
        with a capital letter in the middle of a sentence (names), and plurals whose
        singular is also in the list (see removePlurals). "isn't" counts as "is" and
        "student's" as "student".
    """

    text = SPLIT_WORD.sub(r"\1\2", text)

    # Every possible word, in order of first appearance (a dict keeps the order).
    order = {}
    # Words that were written in lowercase at least once.
    inLowercase = set()
    # Words that were written with a capital letter in the middle of a sentence.
    capitalized = set()

    for eachMatch in WORD.finditer(text):
        # "Note:" / "Example:" at the start of a line is a label, not vocabulary.
        if text.startswith(":", eachMatch.end()):
            continue

        rawToken = eachMatch.group(0).replace("’", "'")
        token = rawToken.split("'", 1)[0]  # "student's" -> "student"

        # "isn't" -> "is", "don't" -> "do" (never "isn" or "don").
        if rawToken.lower().endswith("n't"):
            token = NOT_ENDING.sub("", rawToken)
            token = CONTRACTION_STEMS.get(token.lower(), token)

        lowered = token.lower()

        if len(lowered) < MIN_PASSAGE_WORD_LENGTH or isCommonWord(lowered):
            continue

        order[lowered] = None

        if not token[0].isupper():
            inLowercase.add(lowered)
        elif not isSentenceStart(text, eachMatch.start()):
            capitalized.add(lowered)

    # A word written with a capital letter in the middle of a sentence, and never in
    # lowercase, is usually a name.
    words = [
        eachWord
        for eachWord in order
        if eachWord in inLowercase or eachWord not in capitalized
    ]

    return removePlurals(words)


def isSentenceStart(text: str, position: int) -> bool:
    """
    Tell whether the word at this position starts a sentence or a line (so its capital
    letter says nothing about it being a name).

    Parameters:
        Mandatory:
            - text (str): The passage.
            - position (int): Where the word starts in the text.
    Returns:
        bool: True at the start of the text, or when the last character before the word
        (ignoring spaces, tabs, quotes and an opening bracket, at most 6 characters
        back) is . ! ? : or a line break. Otherwise False.
    """

    before = text[max(0, position - 6) : position].rstrip(" \t\"'“‘(")

    if position == 0 or before == "":
        return True

    return before[-1] in ".!?:\n\r"


def removePlurals(words: list[str]) -> list[str]:
    """
    Drop simple plural forms when the singular is also in the list: "cats" (with "cat"),
    "boxes" (with "box"), "stories" (with "story").

    Parameters:
        Mandatory:
            - words (list[str]): Words in lowercase, each once.
    Returns:
        list[str]: The same words in the same order, without the plurals whose
        singular is also in the list. A plural on its own is kept.
    """

    wordSet = set(words)

    def isPlural(word: str) -> bool:
        """
        Tell whether a word is the -s, -es or -ies plural of another word in the list.

        Parameters:
            Mandatory:
                - word (str): The word to check.
        Returns:
            bool: True if its singular ("stories" -> "story", "boxes" -> "box",
            "cats" -> "cat") is also in the list, otherwise False.
        """

        return (
            (word.endswith("ies") and word[:-3] + "y" in wordSet)
            or (word.endswith("es") and word[:-2] in wordSet)
            or (word.endswith("s") and word[:-1] in wordSet)
        )

    return [eachWord for eachWord in words if not isPlural(eachWord)]


def extractWords(text: str) -> list[str]:
    """
    Find the vocabulary in some text: a word list gives one word per line,
    a passage gives its less common words. Duplicates are removed (ignoring case), order
    is kept.

    Parameters:
        Mandatory:
            - text (str): The text read from a file (see readTextFromFile).
    Returns:
        list[str]: The words found, each once, in the order they appear: the words of
        a word list as written (see wordsFromList), or the words of a passage in
        lowercase (see wordsFromPassage). Can be empty.
    """

    text = cleanText(text)

    if looksLikeWordList(text):
        return uniqueWords(wordsFromList(text))

    return uniqueWords(wordsFromPassage(text))


def uniqueWords(words: list[str]) -> list[str]:
    """
    Remove repeated words, ignoring upper / lower case.

    Parameters:
        Mandatory:
            - words (list[str]): The words, possibly with repeats.
    Returns:
        list[str]: Each word once, in order of first appearance, written the way it
        first appeared ("Cat", "cat" -> "Cat").
    """

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

    Parameters:
        Mandatory:
            - words (list[str]): The words found in a file.
            - cards (list[Card]): The deck.
    Returns:
        list[str]: The words that are not in the deck yet, in the same order. Words are
        compared the way cardDeck.findCard compares them: ignoring upper / lower case
        and spaces around the word.
    """

    # The same comparison as cardDeck.findCard, but one set lookup per word instead of a
    # search of the deck.
    knownWords = {eachCard.word.casefold() for eachCard in cards}
    return [
        eachWord for eachWord in words if eachWord.strip().casefold() not in knownWords
    ]


# ---------- Choosing words ----------


def parseSelection(answer: str, count: int) -> list[int] | None:
    """
    Turn the user's choice on the import screen into item indexes (starting from 0).

    Parameters:
        Mandatory:
            - answer (str): What the user typed: "" (just Enter), "a" or "all" for
              everything; "n", "no" or "none" for nothing; or numbers and ranges from 1,
              separated by commas or spaces, like "1,3,5-8" (a range may be written
              backwards: "8-5"). Upper / lower case does not matter.
            - count (int): How many items are on the list.
    Returns:
        list[int] | None: The chosen indexes (number - 1), each once, in the order
        typed. An empty list for "none". None when the answer is not valid: a part that
        is not a number or a range, or a number outside 1 to count.
    """

    answer = answer.strip().lower()

    if answer in ["", "a", "all"]:
        return list(range(count))

    if answer in ["n", "no", "none"]:
        return []

    indexes = {}  # used as an ordered set: each index once, in the order typed

    for eachPart in SELECTION_SEPARATOR.split(answer):
        if eachPart == "":
            continue

        rangeMatch = NUMBERS.fullmatch(eachPart)

        if rangeMatch is not None:
            start, end = sorted((int(rangeMatch.group(1)), int(rangeMatch.group(2))))
            numbers = range(start, end + 1)
        elif eachPart.isdigit():
            numbers = [int(eachPart)]
        else:
            return None

        for eachNumber in numbers:
            if not 1 <= eachNumber <= count:
                return None
            indexes[eachNumber - 1] = None

    return list(indexes)


def askWhichWords(words: list[str]) -> list[str] | None:
    """
    Show the found words in numbered columns and let the user choose which ones to add.
    An answer that is not valid is explained, and the question is asked again.

    Parameters:
        Mandatory:
            - words (list[str]): The words found in the file and not yet in the deck.
    Returns:
        list[str] | None: The chosen words (see parseSelection), which can be empty for
        "none". None if the user wants to go back (q, Ctrl+C or Ctrl+Z / Ctrl+D).
    """

    numberWidth = len(str(len(words)))
    wordWidth = terminalDisplay.MAX_WORD_COLUMN_WIDTH
    items = [
        f"{index:>{numberWidth}}. {terminalDisplay.truncateText(eachWord, wordWidth)}"
        for index, eachWord in enumerate(words, start=1)
    ]

    print(terminalDisplay.formatColumns(items))
    print()
    print(ChatColor.paint("Which words do you want to add?", ChatColor.BOLD))
    print(
        ChatColor.paint(
            "  Enter = all,  e.g. 1,3,5-8 = some,  n = none", ChatColor.DARK_GRAY
        )
    )

    while True:
        answer = ask("Your choice: ", ChatColor.YELLOW)

        if isQuit(answer):
            return None

        indexes = parseSelection(answer, len(words))

        if indexes is not None:
            return [words[eachIndex] for eachIndex in indexes]

        print(
            ChatColor.paint(
                f"Please type numbers from 1 to {len(words)}, e.g. 1,3,5-8.",
                ChatColor.ORANGE,
            )
        )


# ---------- Adding words to the deck ----------


def createCard(word: str) -> tuple[Card | None, str]:
    """
    Look up a word and turn it into a card (with a Chinese translation if the AI tutor
    is set up). A failed translation is not a problem: the card just has none.

    Parameters:
        Mandatory:
            - word (str): The word to look up.
    Returns:
        tuple[Card | None, str]: (card, "") when the word was found, or (None, reason)
        when it was skipped. The reason is short text for the progress line: "not
        found in the dictionary" or "could not reach the dictionary (...)".
    """

    try:
        result = connectFreeDictionaryAPI.getWordDefinition(word)
    except requests.RequestException as error:
        return None, f"could not reach the dictionary ({error})"

    if not result["definitions"]:
        return None, "not found in the dictionary"

    translation = ""
    if genAITutor.isAIAvailable():
        try:
            translation = genAITutor.translateWord(
                result["word"], result["definitions"][0]
            )
        except Exception:
            translation = ""

    return Card.fromLookup(result, translation), ""


def addWords(
    words: list[str],
    cards: list[Card],
    deckPath: str,
    translations: dict[str, str] | None = None,
) -> dict:
    """
    Look up each word and add it to the deck, showing progress line by line.
    The deck is saved after every word, so nothing is lost if the user stops.
    If the deck file cannot be written, that word is taken out again and the import
    stops.

    Parameters:
        Mandatory:
            - words (list[str]): The words to add (at least one).
            - cards (list[Card]): The deck. It is changed in place.
            - deckPath (str): The deck file.
        Optional:
            - translations (dict[str, str] | None): {word in lowercase: translation},
              e.g. from the Chinese column of a CSV file (see readCSVTranslations). A
              translation found here wins over the AI tutor's.
              Default: None (no translations given).
    Returns:
        dict: {"added": int, "skipped": int}: how many words were added, and how many
        were skipped (not found, already in the deck, or not saved).
    """

    summary = {"added": 0, "skipped": 0}
    wordWidth = max(map(len, words))
    counterWidth = len(str(len(words)))

    for index, eachWord in enumerate(words, start=1):
        counter = ChatColor.paint(
            f"  [{index:>{counterWidth}}/{len(words)}] ", ChatColor.DARK_GRAY
        )
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
            print(
                start
                + ChatColor.paint(
                    f'skipped: "{card.word}" is already in your deck',
                    ChatColor.DARK_GRAY,
                )
            )
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
    If the AI tutor is set up and the text is a passage, offer to let it pick the most
    useful words. Falls back to the words found without AI if it fails.

    Parameters:
        Mandatory:
            - text (str): The text of the file.
            - words (list[str]): The words found without AI (see extractWords).
    Returns:
        list[str]: The words the AI tutor picked, or the given words unchanged when the
        tutor is not set up, the text is a word list, the user says no, the tutor
        cannot be reached, or it picks nothing.
    """

    if not genAITutor.isAIAvailable() or looksLikeWordList(text):
        return words

    if not askYesNo(
        "Let the AI tutor pick the most useful words? (Y/n) ", default=True
    ):
        return words

    print(ChatColor.paint("Asking the AI tutor...", ChatColor.BLUE))

    try:
        picked = genAITutor.pickVocabulary(text)
    except Exception as error:
        print(
            ChatColor.paint(f"Could not reach the AI tutor: {error}", ChatColor.ORANGE)
        )
        return words

    if not picked:
        print(
            ChatColor.paint(
                "The AI tutor did not pick any words, so all found words are shown.",
                ChatColor.ORANGE,
            )
        )
        return words

    return picked


def importVocabulary(cards: list[Card], deckPath: str) -> None:
    """
    The "Import words from a file" screen: ask for a file, find the vocabulary in it,
    let the user choose words, and add them to the deck.
    Words already in the deck are hidden, and at most MAX_IMPORT_WORDS (100) words are
    offered at once. Enter (or q) at the file question goes back to the main menu.

    Parameters:
        Mandatory:
            - cards (list[Card]): The deck. It is changed in place.
            - deckPath (str): The deck file, saved after every added word.
    """

    print(
        ChatColor.paint(
            "Import words from a text, CSV, PDF, Word (.docx) or image file.",
            ChatColor.DARK_GRAY,
        )
    )
    print(
        ChatColor.paint(
            "Tip: you can drag the file into this window to type its path.",
            ChatColor.DARK_GRAY,
        )
    )
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

    extension = os.path.splitext(path)[1].lower()
    translations = {}
    if extension in CSV_DELIMITERS:
        translations = readCSVTranslations(path, CSV_DELIMITERS[extension])

    words = chooseWordsWithAI(text, extractWords(text))

    foundCount = len(words)
    words = removeKnownWords(words, cards)
    knownCount = foundCount - len(words)

    if not words:
        if knownCount > 0:
            print(
                ChatColor.paint(
                    f"All {knownCount} words in this file are already in your deck.",
                    ChatColor.GREEN,
                )
            )
        else:
            print(
                ChatColor.paint(
                    "No English words were found in this file.", ChatColor.ORANGE
                )
            )
        return

    hiddenCount = max(0, len(words) - MAX_IMPORT_WORDS)
    words = words[:MAX_IMPORT_WORDS]

    terminalDisplay.printHeading(f"Words found in {os.path.basename(path)}")

    notes = []
    if knownCount > 0:
        notes.append(f"{knownCount} already in your deck are hidden")
    if hiddenCount > 0:
        notes.append(f"only the first {MAX_IMPORT_WORDS} are shown")
    if notes:
        print(ChatColor.paint("  (" + "; ".join(notes) + ")", ChatColor.DARK_GRAY))
        print()

    selectedWords = askWhichWords(words)
    if not selectedWords:
        print(ChatColor.paint("No words added.", ChatColor.DARK_GRAY))
        return

    terminalDisplay.printHeading(f"Adding {len(selectedWords)} words")

    summary = addWords(selectedWords, cards, deckPath, translations)

    print()
    print(
        ChatColor.paint(
            f"Added {summary['added']}, skipped {summary['skipped']}.",
            ChatColor.BOLD,
            ChatColor.GREEN,
        )
    )
