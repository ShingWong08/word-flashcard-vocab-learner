# CEFR Vocabulary Level Scanner for English Documents

[中文](README.md) | **English**

Scans PDF, Word, Excel, images, and plain text files, determines the CEFR level (A1–C2) of every English word,
and automatically collects the advanced **B2–C2** words and phrases into a vocabulary book with English
definitions and example sentences taken from the source.

## Features

- Supports PDF (.pdf), Word (.docx), Excel (.xlsx), images (.png/.jpg/.tiff), and plain text (.txt/.csv/.md/.html)
- Accepts a single file, multiple files, or an entire folder (scanned recursively)
- Handles scanned PDFs: automatically detects PDFs with no text layer and falls back to Apple Vision OCR (macOS)
- Bundled CEFR dictionary (A1–C2, ~10,000 entries; sources listed in `data/SOURCES.md`)
- Lemmatization (run/runs/ran → run) and English definitions (WordNet, works offline)
- Optional translation: translate each word into a target language (Traditional Chinese, Simplified Chinese, Japanese, Korean, Spanish, French, etc.), translating only the word itself
- Multiple export formats for importing into dictionaries or flashcard apps

## Installation

```bash
cd vocabulary_scanner
python3 -m pip install -r requirements.txt
python3 -m nltk.downloader wordnet omw-1.4   # required on first run, for definitions and lemmatization
```

> If nltk cannot be installed or WordNet cannot be downloaded, the program still runs — it simply skips
> lemmatization and English definitions and falls back to matching the surface form. The CEFR-J dictionary
> already contains many inflected forms, so coverage remains reasonably good.

### OCR (macOS, optional)

OCR uses Apple's built-in Vision framework, so Tesseract is not needed. Requirements:

- macOS with **Xcode Command Line Tools** (`swiftc` available). Run `xcode-select --install` in Terminal.
- On first use, the program compiles `ocr/vision_ocr.swift` into `build/vision_ocr` automatically.

OCR only triggers when a PDF has **no text layer** (`--ocr auto`, the default). Native text PDFs never go
through OCR, so their speed is unaffected.

### Translation (optional)

Translation uses Google Translate via `deep-translator` and requires a network connection. Results are cached
in `data/translations/`, so the same words can be translated offline afterwards without hitting the network again.

## Usage

### The easiest way: never type a path by hand

Paths that contain spaces (e.g. `Group 6_TAM ... Final Version.docx`) must be quoted, and a single missing
quote is enough to make the command fail. The simplest approach is to let Terminal paste the path for you:

1. Open Terminal and type `python3 vocab_scanner.py`, **leaving a trailing space**
2. Drag the file (or a whole folder) from Finder into the Terminal window — the path is pasted automatically and quoted for you
3. Press Enter

Run the command from inside the `vocabulary_scanner/` folder. To drag a file in, open a second Finder window at the file's location.

> Every option is optional. Without `--out-dir` the results always go to `output/`; the flag only changes the
> output folder so a previous run is not overwritten, e.g. `--out-dir output/essay`.

### Command examples

```bash
# Scan an entire folder
python3 vocab_scanner.py sample/

# Scan multiple files
python3 vocab_scanner.py report.pdf notes.docx data.xlsx

# Merge into an existing vocabulary book (accumulate counts, keep sources)
python3 vocab_scanner.py new_docs/ --merge output/vocabulary_book.csv

# Look up the level of a single word
python3 vocab_scanner.py --lookup ambiguous

# Scan and translate the words into Traditional Chinese (words only, not definitions)
python3 vocab_scanner.py sample/ --translate zh-TW

# Language names or codes both work, e.g. zh-CN (Simplified Chinese), ja (Japanese), ko (Korean), es (Spanish), fr (French)
python3 vocab_scanner.py sample/ --translate 日文

# Force OCR for every PDF (usually unnecessary)
python3 vocab_scanner.py scans/ --ocr force

# Disable OCR entirely
python3 vocab_scanner.py scans/ --ocr off
```

## Options

| Option | Description | Default |
|------|------|------|
| `inputs` | Files or folders (multiple allowed) | none |
| `--out-dir` | Output folder | `output/` |
| `--min-level` | Lowest level included in the vocabulary book | `B2` |
| `--max-level` | Highest level included in the vocabulary book | `C2` |
| `--merge` | Merge into an existing `vocabulary_book.csv` | none |
| `--sort` | Sort order: `level` (by level) or `count` (by frequency) | `level` |
| `--top` | Number of unknown words shown in the report | `30` |
| `--no-definitions` | Skip WordNet English definitions | none |
| `--lookup` | Look up one word's level, then exit | none |
| `--ocr` | OCR mode: `auto` = only when there is no text layer, `force` = always OCR PDFs, `off` = disabled | `auto` |
| `--ocr-dpi` | Resolution used to render PDF pages for OCR | `200` |
| `--translate` | Translate words into the given language (`zh-TW`, `zh-CN`, `ja`, `ko`, `es`, `fr`, …); words only | none |

## Output (written to `output/` by default)

| File | Purpose |
|------|------|
| `vocabulary_book.xlsx` | Excel vocabulary book (includes a "Translation" column and a level statistics sheet) |
| `vocabulary_book.csv` | CSV vocabulary book; use this file with `--merge` |
| `vocabulary_anki.tsv` | Anki import file (word / definition / example / level) |
| `vocabulary_eudic.txt` | Word list for Eudic, Youdao, and similar apps (one word per line) |
| `vocabulary_book.json` | JSON format |
| `analysis_report.txt` | Full analysis report (level distribution + advanced word list) |

## Importing into Dictionaries / Flashcard Apps

- **Anki**: File → Import → select `vocabulary_anki.tsv`, set the separator to "Tab",
  then map the fields to word, definition, example, level, part of speech, and translation.
- **Eudic**: Learning → Vocabulary Book → Import → select `vocabulary_eudic.txt` (one word per line).
- **Youdao / others**: Most apps accept a `.txt` with one word per line, so `vocabulary_eudic.txt` works there too.

## Level Assignment Rules

- A word is first matched on its lowercase, accent-stripped surface form; if that fails, it is lemmatized with
  WordNet and matched again.
- If a word appears in several levels, the **lower** level wins (following the CEFR convention that a word is
  acquired at the earliest level it appears in), while `all_levels` retains every level.
- Phrases (e.g. `climate change`) are matched as 2–4 word sequences and listed separately from single words.

## Notes

- Legacy Word `.doc` and Excel `.xls` files are not supported directly; save them as `.docx` / `.xlsx` first.
- Scanned PDFs are processed with OCR automatically; a higher resolution (`--ocr-dpi`) is more accurate but
  slower, so be patient with long documents.
- Translation requires network access; the first batch of new words is slow, but later runs hit the cache
  (`data/translations/`) and are fast.
- CEFR levels are approximate: the same word can sit at different levels in different contexts or parts of speech.
