import importlib.util

import pytest

from word_flashcard_vocab_learner import cardDeck, genAITutor, importVocabulary
from word_flashcard_vocab_learner import connectFreeDictionaryAPI as dictionary
from word_flashcard_vocab_learner.flashCard import Card


def makePDF(path, pageTexts):
    """
    Write a small but real PDF. Each item of pageTexts is one page; "" makes a page
    without text (like a scanned page). Each line of a page's text becomes one line in
    the PDF.
    """

    pageCount = len(pageTexts)
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(pageCount))

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {pageCount} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    for index, eachText in enumerate(pageTexts):
        contentNumber = 5 + 2 * index
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {contentNumber} 0 R >>"
        )

        if eachText == "":
            stream = ""
        else:
            lines = " Tj T* ".join(
                f"({eachLine})" for eachLine in eachText.splitlines()
            )
            stream = f"BT /F1 12 Tf 14 TL 72 720 Td {lines} Tj ET"

        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")

    output = b"%PDF-1.4\n"
    offsets = []

    for number, eachObject in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n{eachObject}\nendobj\n".encode("latin-1")

    xrefStart = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    for eachOffset in offsets:
        output += f"{eachOffset:010d} 00000 n \n".encode("latin-1")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xrefStart}\n%%EOF\n"
    )
    output += trailer.encode("latin-1")

    path.write_bytes(output)


# ---------- Reading files ----------


def testCleanPathRemovesQuotes(tmp_path):
    assert importVocabulary.cleanPath(f'  "{tmp_path}"  ') == str(tmp_path)
    assert importVocabulary.cleanPath("'notes.txt'") == "notes.txt"


def testReadTextFileWithByteOrderMark(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("ambiguous\n含糊", encoding="utf-8-sig")

    assert importVocabulary.readTextFromFile(str(path)) == "ambiguous\n含糊"


def testReadCsvTakesFirstColumnEvenWithLineBreaksInCells(tmp_path):
    path = tmp_path / "deck.csv"
    path.write_text(
        'Word,Definitions\ncat,"1. a pet\n2. a person"\ndog,a pet\n', encoding="utf-8"
    )

    text = importVocabulary.readTextFromFile(str(path))

    assert text == "Word\ncat\ndog"
    assert importVocabulary.extractWords(text) == ["cat", "dog"]


def testReadPdf(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "notes.pdf"
    makePDF(
        path, ["ambiguous - unclear\nreluctant - not willing", "hypothesis - an idea"]
    )

    text = importVocabulary.readTextFromFile(str(path))

    assert importVocabulary.extractWords(text) == [
        "ambiguous",
        "reluctant",
        "hypothesis",
    ]


def testScannedPdfNeedsOcr(tmp_path, monkeypatch):
    pytest.importorskip("pypdf")
    path = tmp_path / "scan.pdf"
    makePDF(path, [""])
    monkeypatch.setattr(importVocabulary, "isOCRAvailable", lambda: False)

    with pytest.raises(importVocabulary.FileImportError, match="looks scanned"):
        importVocabulary.readTextFromFile(str(path))


def testScannedPdfPagesAreReadWithOcr(tmp_path, monkeypatch):
    pytest.importorskip("pypdf")
    path = tmp_path / "mixed.pdf"
    makePDF(path, ["ambiguous - unclear", ""])

    renderedPages = []

    def fakeRender(pdfPath, pageIndexes):
        renderedPages.extend(pageIndexes)
        return ["page image"] * len(pageIndexes)

    monkeypatch.setattr(importVocabulary, "isOCRAvailable", lambda: True)
    monkeypatch.setattr(importVocabulary, "renderPDFPages", fakeRender)
    monkeypatch.setattr(
        importVocabulary, "runOCR", lambda image: "reluctant - not willing"
    )

    text = importVocabulary.readTextFromFile(str(path))

    assert renderedPages == [1]
    assert importVocabulary.extractWords(text) == ["ambiguous", "reluctant"]


def testReadWordDocumentParagraphsAndTables(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "words.docx"

    document = docx.Document()
    document.add_paragraph("ambiguous - unclear")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "reluctant"
    table.rows[0].cells[1].text = "不情願"
    document.save(str(path))

    text = importVocabulary.readTextFromFile(str(path))

    assert importVocabulary.extractWords(text) == ["ambiguous", "reluctant"]


def testReadImageUsesOcr(tmp_path, monkeypatch):
    image = pytest.importorskip("PIL.Image")
    path = tmp_path / "scan.png"
    image.new("RGB", (20, 20), "white").save(path)
    monkeypatch.setattr(
        importVocabulary, "runOCR", lambda picture: "ambiguous\nreluctant"
    )

    assert importVocabulary.readTextFromFile(str(path)) == "ambiguous\nreluctant"


def testMissingAndUnsupportedFiles(tmp_path):
    with pytest.raises(importVocabulary.FileImportError, match="not found"):
        importVocabulary.readTextFromFile(str(tmp_path / "nothing.pdf"))

    oldWordFile = tmp_path / "old.doc"
    oldWordFile.write_bytes(b"x")
    with pytest.raises(importVocabulary.FileImportError, match="save it as .docx"):
        importVocabulary.readTextFromFile(str(oldWordFile))

    music = tmp_path / "song.mp3"
    music.write_bytes(b"x")
    with pytest.raises(
        importVocabulary.FileImportError, match="Unsupported file type '.mp3'"
    ):
        importVocabulary.readTextFromFile(str(music))


@pytest.mark.skipif(
    importlib.util.find_spec("pytesseract") is not None,
    reason="pytesseract is installed",
)
def testOcrWithoutPytesseractGivesInstallHint():
    with pytest.raises(importVocabulary.FileImportError, match="ocr"):
        importVocabulary.runOCR(None)


def testFindTesseractUsesSetting(tmp_path, monkeypatch):
    program = tmp_path / "tesseract.exe"
    program.write_bytes(b"")
    monkeypatch.setenv("TESSERACT_CMD", str(program))

    assert importVocabulary.findTesseract() == str(program)


# ---------- Finding words ----------


@pytest.mark.parametrize(
    "line, expected",
    [
        ("ambiguous", "ambiguous"),
        ("1. ambiguous - unclear", "ambiguous"),
        ("2) reluctant: not willing", "reluctant"),
        ("• ice cream (n.) 雪糕", "ice cream"),
        ("banana 香蕉", "banana"),
        ("well-known - famous", "well-known"),
        ("ambiguous adj. unclear", "ambiguous"),
        ("3、hypothesis，假設", "hypothesis"),
        ("香蕉", None),
        ("", None),
    ],
)
def testWordFromListLine(line, expected):
    assert importVocabulary.wordFromListLine(line) == expected


def testWordListSkipsHeadingLines():
    text = "Unit 3 vocabulary\nWord list\nWord\nunit - 單元\nreluctant - not willing\n"
    assert importVocabulary.extractWords(text) == ["unit", "reluctant"]


@pytest.mark.parametrize(
    "word, expected",
    [
        ("showed", True),
        ("making", True),
        ("stopped", True),
        ("earlier", True),
        ("friends", True),
        ("reluctant", False),
        ("experiments", False),
        ("research", False),
    ],
)
def testIsCommonWord(word, expected):
    assert importVocabulary.isCommonWord(word) is expected


def testWordListIsDetected():
    assert importVocabulary.looksLikeWordList("cat\ndog - 狗\n3. bird\n") is True
    assert (
        importVocabulary.looksLikeWordList(
            "This is a long sentence about many things.\nAnd another long one here."
        )
        is False
    )


def testMarkdownFrontMatterAndLinksDoNotHideTheWords():
    text = (
        "---\n"
        "title: test\n"
        "---\n"
        "\n"
        "Visit https://example.com or www.test.org for more.\n"
        "The seminar discussed sustainability.\n"
    )

    assert importVocabulary.looksLikeWordList(text) is False
    assert importVocabulary.extractWords(text) == [
        "visit",
        "seminar",
        "discussed",
        "sustainability",
    ]


def testNoteLinesAreProseNotAWordList():
    text = (
        "Note: the seminar discussed sustainability.\n"
        "Example: biodiversity matters.\n"
        "Deforestation is a problem.\n"
    )

    assert importVocabulary.looksLikeWordList(text) is False
    assert importVocabulary.extractWords(text) == [
        "seminar",
        "discussed",
        "sustainability",
        "biodiversity",
        "matters",
        "deforestation",
    ]


def testLinksAndEmailsLeaveNoWordFragments():
    text = (
        "Visit https://example.com today.\n"
        "Read www.test.org daily.\n"
        "Email me at a@b.com please.\n"
    )

    assert importVocabulary.extractWords(text) == ["visit", "daily", "email"]


def testShortWordsComeFromAPassage():
    assert importVocabulary.extractWords("The cat sat on the mat with a dog.") == [
        "cat",
        "sat",
        "mat",
        "dog",
    ]


def testContractionsDoNotLeaveWordStems():
    assert importVocabulary.extractWords(
        "I couldn't visit the museum; she isn't well."
    ) == ["visit", "museum"]


def testWordListWithMeaningsIsStillAList():
    assert importVocabulary.extractWords("cat - 狗\nmat - 垫子\n3. dog\n") == [
        "cat",
        "mat",
        "dog",
    ]


def testCleanTextRemovesFrontMatterLinksAndEmails():
    text = (
        "\ufeff---\ntitle: test\n---\n\nSee https://example.com or mail me at a@b.com\n"
    )

    cleaned = importVocabulary.cleanText(text)

    assert "title" not in cleaned
    assert "https" not in cleaned
    assert "@" not in cleaned
    assert "See" in cleaned


def testWordsFromPassageSkipsCommonWordsAndNames():
    text = (
        "Scientists were reluctant to accept the hypothesis.\n"
        "Mary said the results were ambiguous, "
        "but other scientists disagreed with Mary."
    )

    assert importVocabulary.extractWords(text) == [
        "scientists",
        "reluctant",
        "accept",
        "hypothesis",
        "results",
        "ambiguous",
        "disagreed",
    ]


def testWordsFromPassageJoinsWordsSplitAcrossLines():
    assert "vocabulary" in importVocabulary.wordsFromPassage(
        "You need a large vocab-\nulary to read this book quickly."
    )


def testRemovePlurals():
    assert importVocabulary.removePlurals(
        ["cat", "cats", "story", "stories", "box", "boxes", "news"]
    ) == ["cat", "story", "box", "news"]


def testRemoveKnownWords():
    cards = [Card("Cat", ["a pet"])]
    assert importVocabulary.removeKnownWords(["cat", "dog"], cards) == ["dog"]


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("", [0, 1, 2, 3, 4]),
        ("all", [0, 1, 2, 3, 4]),
        ("n", []),
        ("1,3", [0, 2]),
        ("2-4", [1, 2, 3]),
        ("5 1 1", [4, 0]),
        ("4-2", [1, 2, 3]),
        ("6", None),
        ("0", None),
        ("abc", None),
    ],
)
def testParseSelection(answer, expected):
    assert importVocabulary.parseSelection(answer, 5) == expected


# ---------- Adding words ----------


def testAddWordsSkipsUnknownAndDuplicateWords(monkeypatch, tmp_path, capsys):
    def fakeGetWordDefinition(word):
        if word == "qwzx":
            return {"word": word, "definitions": [], "examples": []}
        return {
            "word": word.lower(),
            "definitions": [f"meaning of {word}"],
            "examples": [[]],
        }

    monkeypatch.setattr(dictionary, "getWordDefinition", fakeGetWordDefinition)
    cards = [Card("cat", ["a pet"])]
    path = str(tmp_path / "deck.json")

    summary = importVocabulary.addWords(["ambiguous", "qwzx", "CAT"], cards, path)

    out = capsys.readouterr().out
    assert summary == {"added": 1, "skipped": 2}
    assert "not found in the dictionary" in out
    assert "already in your deck" in out
    assert [eachCard.word for eachCard in cardDeck.loadDeck(path)] == [
        "cat",
        "ambiguous",
    ]


def testCreateCardAddsTranslationWhenAiIsSetUp(monkeypatch, enableAI):
    monkeypatch.setattr(
        dictionary,
        "getWordDefinition",
        lambda word: {"word": word, "definitions": ["unclear"], "examples": [[]]},
    )
    monkeypatch.setattr(
        genAITutor, "translateWord", lambda word, definition: "含糊不清"
    )

    card, reason = importVocabulary.createCard("ambiguous")

    assert reason == ""
    assert card.translation == "含糊不清"


def testRunImportLetsAiPickWordsFromAPassage(
    monkeypatch, tmp_path, typeAnswers, capsys, enableAI
):
    passage = tmp_path / "article.txt"
    passage.write_text(
        "The ending of the story was ambiguous, and many readers were reluctant "
        "to guess what happened next.",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        genAITutor, "pickVocabulary", lambda text: ["ambiguous", "reluctant"]
    )
    monkeypatch.setattr(genAITutor, "translateWord", lambda word, definition: "")
    monkeypatch.setattr(
        dictionary,
        "getWordDefinition",
        lambda word: {"word": word, "definitions": ["x"], "examples": [[]]},
    )

    cards = []
    typeAnswers([str(passage), "y", "2"])

    importVocabulary.importVocabulary(cards, str(tmp_path / "deck.json"))

    assert [eachCard.word for eachCard in cards] == ["reluctant"]
    assert "Added 1, skipped 0." in capsys.readouterr().out


def testRunImportReportsFileErrors(tmp_path, typeAnswers, capsys):
    typeAnswers([str(tmp_path / "missing.pdf")])

    importVocabulary.importVocabulary([], str(tmp_path / "deck.json"))

    assert "File not found" in capsys.readouterr().out


def testRunImportWhenAllWordsAreKnown(tmp_path, typeAnswers, capsys):
    wordList = tmp_path / "words.txt"
    wordList.write_text("cat\n", encoding="utf-8")
    typeAnswers([str(wordList)])

    importVocabulary.importVocabulary(
        [Card("cat", ["a pet"])], str(tmp_path / "deck.json")
    )

    assert "already in your deck" in capsys.readouterr().out


def testReadCsvTranslationsUsesTheChineseColumn(tmp_path):
    from word_flashcard_vocab_learner import exportDeckToCSV

    path = tmp_path / "deck.csv"
    exportDeckToCSV.exportDeckToCSV(
        [
            Card(
                "cat", ["a pet"], [["My cat is asleep."]], "貓", nextReview="2026-12-01"
            )
        ],
        str(path),
    )

    translations = importVocabulary.readCSVTranslations(str(path), ",")

    assert translations == {"cat": "貓"}


def testReadCsvTranslationsWithoutATranslationColumn(tmp_path):
    path = tmp_path / "words.csv"
    path.write_text("Word\ncat\ndog\n", encoding="utf-8")

    assert importVocabulary.readCSVTranslations(str(path), ",") == {}


def testImportFillsTheChineseColumnFromTheUsersCsv(
    tmp_path, typeAnswers, capsys, monkeypatch
):
    from word_flashcard_vocab_learner import exportDeckToCSV

    csvPath = tmp_path / "my-words.csv"
    exportDeckToCSV.exportDeckToCSV(
        [Card("cat", ["a pet"], [["My cat is asleep."]], "貓")],
        str(csvPath),
    )
    monkeypatch.setattr(
        dictionary,
        "getWordDefinition",
        lambda word: {"word": word, "definitions": ["a pet"], "examples": [[]]},
    )

    cards = []
    typeAnswers([str(csvPath), "y", ""])

    importVocabulary.importVocabulary(cards, str(tmp_path / "deck.json"))

    assert "Added 1, skipped 0." in capsys.readouterr().out
    assert cards[0].word == "cat"
    assert cards[0].translation == "貓"


def testReadCsvTranslationsWithoutAHeaderRow(tmp_path):
    path = tmp_path / "words.csv"
    path.write_text("cat,貓\ndog,狗\n", encoding="utf-8")

    assert importVocabulary.readCSVTranslations(str(path), ",") == {
        "cat": "貓",
        "dog": "狗",
    }


def testReadCsvTranslationsIgnoresAnEnglishSecondColumn(tmp_path):
    path = tmp_path / "words.csv"
    path.write_text("cat,a small pet\ndog,a pet that barks\n", encoding="utf-8")

    assert importVocabulary.readCSVTranslations(str(path), ",") == {}
