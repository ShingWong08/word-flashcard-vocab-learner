# Word flashcard vocabulary learner

A lightweight command-line flashcard tool that helps students learn English vocabulary.
Look up a word, save it as a flashcard, and review it with spaced repetition until you know it.

## Features

- **Look up words** with English definitions and example sentences ([Free Dictionary API](https://freedictionaryapi.com/), no key needed)
- **Chinese translations** from an LLM (optional, needs `LLM_API_KEY`)
- **Pronunciation** with ElevenLabs text-to-speech (optional, needs `ELEVENLABS_API_KEY`)
- **Flashcard deck** saved as JSON, so your progress is kept between sessions
- **Edit a card** after adding it: fix the spelling, the Chinese translation or the meaning
- **Practise one word** whenever you want, without waiting for its review date
- **Import vocabulary** from text, CSV, PDF, Word (`.docx`) and scanned pages / photos (OCR)
- **Progress screen** with accuracy, cards per box and the words you get wrong most often
- **Export** your deck to CSV for Excel, Google Sheets, Quizlet or Anki
- **Spaced repetition** (Leitner system): cards you know come back less often, cards you forget come back tomorrow
- **Five review modes**:

| Mode | What you do | Needs |
| --- | --- | --- |
| Meaning | See the word, recall its meaning, then mark yourself | – |
| Spelling | Read the definitions (word hidden), the translation and a hint, then type the word | – |
| Listening | Hear the word, then type it | speech |
| Speaking | Read the clues, then say the word into the microphone | speech |
| Sentence | Write a sentence using the word and get feedback from the AI tutor | `LLM_API_KEY` |

## Requirements

- Python 3.10 or newer
- For speech features: the PortAudio library (for recording) and [ffmpeg](https://ffmpeg.org/) on your `PATH` (for playback)
- For importing scans and photos: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
  (on Windows, the [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki) is the easiest)

## Installation

```bash
python -m venv env
env\Scripts\activate          # Windows
# source env/bin/activate     # macOS / Linux

pip install .                 # core features
pip install ".[speech]"       # + speech-to-text / text-to-speech
pip install ".[documents]"    # + import from PDF and Word (.docx)
pip install ".[ocr]"          # + import from scans and photos (also needs Tesseract OCR)
pip install ".[dev]"          # + pytest
```

## API keys and settings

Copy `.env.example` to `.env` and fill in the keys you need. `.env` is git-ignored; never commit it.

| Variable | Used by |
| --- | --- |
| `LLM_API_KEY` | Chinese translations and sentence feedback (`genAITutor`, via `connectGenAI`) |
| `ELEVENLABS_API_KEY` | Pronunciation, Listening and Speaking modes (`textToSpeech`, `speechToText`) |
| `WORD_FLASHCARD_DECK` | Optional. Where the deck is saved. Default: `~/.word_flashcard/deck.json`. A leading `~` is expanded |
| `TESSERACT_CMD` | Optional. Full path of `tesseract.exe` if Tesseract OCR is not on your `PATH` |

Every key is optional: without them the app still looks up words and reviews them in Meaning and Spelling modes.

## Usage

```bash
word-flashcard
```

```
─── Main menu ──────────────────────────────────────────────

  1. Look up and add words
  2. Review cards  (5 due)
  3. Import words from a file (PDF, Word, scan, text)
  4. View my deck
  5. Progress
  6. Export deck to CSV
  7. Remove words
  8. Edit a card
  9. Practise one word

  c. Clear the screen
  q. Quit
```

1. **Look up and add words**: type a word to see its definitions, then press `y` to add it to your deck.
2. **Review cards**: review the cards due today in the mode you choose, 20 cards at a time. Wrong answers
   are asked once more at the end of the session. When more cards are due, you can carry on with the next
   20 straight after the summary. If nothing is due, you can practise all cards without changing your progress.
3. **Import words from a file**: see [Importing vocabulary](#importing-vocabulary).
4. **View my deck**: see every word with its number, box (1–5), next review date, score and translation.
   A long deck is shown 30 words per page (Enter = next page, `q` = back), and a narrow terminal shows
   one card per line instead of a table.
5. **Progress**: words due today and this week, accuracy, cards per box and the words to practise more.
6. **Export deck to CSV**: save your deck as a CSV file. It opens in Excel with Chinese shown correctly,
   and can be imported into Quizlet or Anki, or back into this app.
7. **Remove words**: see [Removing words](#removing-words).
8. **Edit a card**: type the word and press Enter on the questions you want to keep. You can change the
   spelling (a word that is already in the deck is refused), the Chinese translation and the meaning
   (one line). Type `-` to clear the translation or the meaning.
9. **Practise one word**: type the word, pick a mode, and review that card now. Its box and review date
   change like a normal review.

Your answers are saved after every card. If the deck file cannot be written (for example the folder is
read-only), the app says so once and keeps going, so the answers of that session are not lost; it tells
you that the progress was not saved when the session ends.

Type `c` (or `clear` / `cls`) to clear the screen.

### Removing words

The screen shows your words in numbered columns (the same numbers as in **View my deck**). Type what to remove:

| Type | Removes |
| --- | --- |
| `banana, accept` | Those words (separate them with commas) |
| `1,3,5-8` | Those numbers from the list |
| `amb*` | Words that start with `amb` (`*` = any letters, `?` = one letter) |
| `box 1` | Every card in box 1 (`box 5` or `mastered` = words you already know well) |
| `all` | Every word in your deck |

You can mix them, e.g. `banana, 3, 5-8`. The words are shown before anything is removed and you confirm with `y`.
Removing every word needs you to type `delete all`. If any part has a typo, nothing is removed.

- `u` puts back the last removal, with its box, review date and score. You can undo several times.
- `l` shows the list again, `h` shows the help. After each removal the new numbers are shown.
- Before every removal, the old deck is copied to `deck.backup.json` next to your deck.

### Importing vocabulary

Type or drag a file into the window. The app reads the text, finds the vocabulary, and shows a numbered list.
Press Enter to add all of them, type numbers such as `1,3,5-8` to add some, or `n` to add none.
Words already in your deck are hidden. Each word is looked up in the dictionary (and translated, if the AI tutor
is set up) before it is added.

| File | How it is read | Needs |
| --- | --- | --- |
| `.txt`, `.md` | As text | – |
| `.csv`, `.tsv` | First column for the words, plus the Chinese column when the file has one | – |
| `.pdf` | Text of every page; scanned pages are read with OCR | `.[documents]`, OCR for scans |
| `.docx` | Paragraphs and tables | `.[documents]` |
| `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp` | OCR | `.[ocr]` and Tesseract |

How the words are found:

- **Word lists** (most lines are short, e.g. `1. ambiguous - 含糊不清` or `reluctant: not willing`):
  the word at the start of each line is taken. Title lines such as `Unit 3 vocabulary` are skipped.
  A line of prose (it ends with `.`, `!` or `?`), a link or an e-mail address is not a list entry.
- **Passages** (articles, stories, notes): the less common words are taken, skipping words shorter
  than 3 letters, very common words (and their forms, like `showed` or `making`) and names.
  A markdown front matter block (`--- … ---`), links and e-mail addresses are removed first, so they
  are never taken for words.
  If `LLM_API_KEY` is set, you can let the AI tutor pick the most useful words instead.

A CSV exported from this app has a `Chinese` column: importing it again fills in the translation
alongside the dictionary meanings. Only words missing from your deck are added, so importing the same
file twice changes nothing.

Old Word `.doc` files are not supported; save them as `.docx` first.

### How spaced repetition works

Each card sits in a box from 1 to 5. A right answer moves it up one box, a wrong answer sends it back to box 1.

| Box | Next review after |
| --- | --- |
| 1 | 1 day |
| 2 | 2 days |
| 3 | 4 days |
| 4 | 7 days |
| 5 | 14 days |

### Generated files

| Path | Contents |
| --- | --- |
| `~/.word_flashcard/deck.json` | Your flashcards and progress |
| `~/.word_flashcard/deck.backup.json` | A copy of the deck from just before the last removal |
| `translation_cache/zh-TW.json` | Saved translations, so each word is only translated once |
| `audio_cache/words/` | Saved pronunciations, so each word is only generated once |
| `recording/` | Temporary microphone recordings (deleted after transcription) |

The cache folders are created in the folder you run `word-flashcard` from.

If you edit `deck.json` by hand, a missing or wrong value (a null meaning, a box outside 1–5, a counter
saved as text) is repaired when the deck loads, so one bad entry does not stop the app. If the file
cannot be read at all while the app is running, it is copied to `deck.json.damaged` before the deck in
memory is saved over it, so nothing is lost silently.

## Project structure

| Module | Purpose |
| --- | --- |
| `__init__.py` | Command-line app and main menu |
| `flashCard.py` | The `Card` data class |
| `cardDeck.py` | Load, save, back up, add, remove and find cards |
| `leitnerScheduler.py` | Leitner boxes and review dates |
| `reviewCards.py` | Review sessions (`reviewCards()`) and answer checking |
| `importVocabulary.py` | Read text, CSV, PDF, Word and images (OCR) and find the vocabulary in them (`importVocabulary()`) |
| `exportDeckToCSV.py` | Export the deck to CSV (`exportDeckToCSV()`); text that looks like a formula is made harmless |
| `removeWords.py` | The "Remove words" screen (`removeWords()`: by word, number, pattern, box or all, with undo) |
| `showProgress.py` | Progress screen (`showProgress()`) |
| `genAITutor.py` | Chinese translation, sentence feedback and picking vocabulary from a passage (uses `connectGenAI`) |
| `speechHelper.py` | Pronunciation (with cache) and listening for spoken answers (uses `textToSpeech`, `speechToText`) |
| `terminalDisplay.py` | Line wrapping, section headings and columns for readable output |
| `connectFreeDictionaryAPI.py` | Dictionary lookup |
| `connectGenAI.py`, `connectGenAIRequest.py` | LLM API connections |
| `textToSpeech.py`, `speechToText.py` | ElevenLabs speech APIs |
| `userInput.py`, `chatColor.py` | Prompts and coloured terminal output |

## Running tests

```bash
pytest
```

The tests never call the real APIs and never touch your real deck.
