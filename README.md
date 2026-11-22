# Word flashcard vocabulary learner

A terminal app for learning English words. You look a word up, keep it as a flashcard,
and the app asks you about it again after 1, 2, 4, 7 and 14 days (a Leitner system)
until you know it. Translations are in Traditional Chinese, written for Hong Kong
secondary school students.

Definitions and example sentences come from the
[Free Dictionary API](https://freedictionaryapi.com/), which needs no key. With no API
keys at all you can look up, import, review in Meaning and Spelling modes, and export.
An LLM key adds Chinese translations and sentence feedback; an ElevenLabs key adds
pronunciation and the Listening and Speaking modes.

| Review mode | What you do | Needs |
| --- | --- | --- |
| Meaning | See the word, recall its meaning, then mark yourself | Nothing extra |
| Spelling | Read the definitions (word hidden), the translation and a hint, then type the word | Nothing extra |
| Listening | Hear the word, then type it | Speech |
| Speaking | Read the clues, then say the word into the microphone | Speech |
| Sentence | Write a sentence with the word and get feedback from the AI tutor | `LLM_API_KEY` |

## Requirements

- Python 3.10 or newer.
- Speech features: the PortAudio library (for recording) and [ffmpeg](https://ffmpeg.org/)
  on your `PATH` (for playback).
- Importing scans and photos: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract).
  On Windows the [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)
  is the easiest way to get it.

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

Groups can be combined: `pip install ".[speech,documents]"`.

There is also a `requirements.txt` with the same packages and no versions, so
`pip install -r requirements.txt` gets the newest release of each. The optional ones are
commented out; remove the `#` in front of the ones you need. It installs packages only.
The `word-flashcard` command comes from `pip install .`.

## API keys and settings

Copy `.env.example` to `.env` and fill in what you need. `.env` is git-ignored; don't
commit it.

| Variable | Used by |
| --- | --- |
| `LLM_API_KEY` | Chinese translations, sentence feedback and picking words from a passage (`genAITutor`, via `connectGenAI`) |
| `ELEVENLABS_API_KEY` | Pronunciation, Listening and Speaking modes (`textToSpeech`, `speechToText`) |
| `WORD_FLASHCARD_DECK` | Optional. Where the deck is saved. Default: `~/.word_flashcard/deck.json`. A leading `~` is expanded |
| `TESSERACT_CMD` | Optional. Full path of `tesseract.exe` if Tesseract OCR is not on your `PATH` |

The LLM calls go to NVIDIA's OpenAI-compatible endpoint
(`https://integrate.api.nvidia.com/v1`) with the model `deepseek-ai/deepseek-v4.1-flash`,
so `LLM_API_KEY` should be an NVIDIA API key. To use another provider, change the
`baseURL` and `model` defaults in `connectGenAI.py`; any OpenAI-compatible API works.

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

1. **Look up and add words.** Type a word to see its definitions, then press `y` to add
   it to your deck.
2. **Review cards.** Pick a mode and go through the cards due today, 20 at a time. Cards
   you get wrong come back once more at the end of the session. If more than 20 are due,
   you can start the next 20 straight after the summary. If nothing is due, you can
   practise every card without changing your progress.
3. **Import words from a file.** See [Importing vocabulary](#importing-vocabulary).
4. **View my deck.** Every word with its number, box (1 to 5), next review date, score
   and translation. Long decks are split into pages of 30 (Enter for the next page, `q`
   to go back). In a narrow terminal each card gets one line instead of a table row, and
   a very long word or translation is cut short with `…` so the columns stay lined up.
5. **Progress.** Words due today and this week, your accuracy, how many cards are in
   each box, and the words you get wrong most often.
6. **Export deck to CSV.** The file opens in Excel with the Chinese intact, and can be
   imported into Quizlet, Anki, Google Sheets, or back into this app.
7. **Remove words.** See [Removing words](#removing-words).
8. **Edit a card.** Type the word, then press Enter on each question you want to leave
   as it is. You can change the spelling (unless the new spelling is already in the
   deck), the Chinese translation and the meaning (one line). Type `-` to clear the
   translation or the meaning.
9. **Practise one word.** Type the word, pick a mode and review that card now, whatever
   its review date. Its box and next review date change as in a normal review.

`c`, `clear` or `cls` clears the screen.

Answers are saved after every card. If the deck file can't be written (a read-only
folder, for example), the app tells you once and carries on, so you don't lose the rest
of the session. When the session ends it reminds you that the progress was not saved.

### Removing words

The screen lists your words in numbered columns, using the same numbers as **View my
deck**. Then type what to remove:

| Type | Removes |
| --- | --- |
| `banana, accept` | Those words (separate them with commas) |
| `1,3,5-8` | Those numbers from the list |
| `amb*` | Words that start with `amb` (`*` = any letters, `?` = one letter) |
| `box 1` | Every card in box 1 (`box 5` or `mastered` = the words you already know well) |
| `all` | Every word in your deck |

You can mix them, e.g. `banana, 3, 5-8`. The app shows what it is about to remove and
waits for `y`. Removing everything needs you to type `delete all`. If any part of what
you typed has a typo, nothing is removed.

- `u` undoes the last removal and puts the cards back with their box, review date and
  score. You can undo more than once.
- `l` shows the list again and `h` shows the help. The new numbers are shown after
  every removal.
- Before each removal the deck is copied to `deck.backup.json`, next to the deck file.

### Importing vocabulary

Type the path of a file or drag it into the window. The app reads it, picks out the
vocabulary and shows a numbered list, leaving out words already in your deck. Press
Enter to add them all, type numbers such as `1,3,5-8` to add some, or `n` to add none.
Each word is looked up in the dictionary, and translated if the AI tutor is set up,
before it is added.

| File | How it is read | Needs |
| --- | --- | --- |
| `.txt`, `.md` | As text | Nothing extra |
| `.csv`, `.tsv` | The first column for the words, plus the Chinese column if there is one | Nothing extra |
| `.pdf` | The text of every page; scanned pages go through OCR | `.[documents]`, plus OCR for scans |
| `.docx` | Paragraphs and tables | `.[documents]` |
| `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp` | OCR | `.[ocr]` and Tesseract |

Old Word `.doc` files are not supported. Save them as `.docx` first.

The app decides whether a file is a word list or a passage, and treats the two
differently.

A word list is a file where most lines are short, like `1. ambiguous - 含糊不清` or
`reluctant: not willing`. The word at the start of each line is taken. Title lines such
as `Unit 3 vocabulary` are skipped, and so is a line that reads like prose (it ends in
`.`, `!` or `?`), a link or an e-mail address.

A passage is an article, a story or a page of notes. The app takes the less common words
and skips names, words shorter than 3 letters, and very common words along with their
forms (`showed`, `making`). Markdown front matter (`--- … ---`), links and e-mail
addresses are removed before it starts, so none of them turn up as words. If
`LLM_API_KEY` is set, you can ask the AI tutor to pick the most useful words instead.

A CSV exported from this app has a `Chinese` column, so importing it again brings the
translations back along with the dictionary meanings. Only words that are not in your
deck are added, which means importing the same file twice changes nothing.

### How spaced repetition works

Every card is in one of five boxes. A right answer moves it up a box; a wrong answer
sends it back to box 1.

| Box | Next review after |
| --- | --- |
| 1 | 1 day |
| 2 | 2 days |
| 3 | 4 days |
| 4 | 7 days |
| 5 | 14 days |

### Files the app creates

| Path | Contents |
| --- | --- |
| `~/.word_flashcard/deck.json` | Your flashcards and progress |
| `~/.word_flashcard/deck.backup.json` | The deck as it was just before the last removal |
| `translation_cache/zh-TW.json` | Saved translations, so each word is translated only once |
| `audio_cache/words/` | Saved pronunciations, so each word is generated only once |
| `recording/` | Microphone recordings, deleted after transcription |

The cache and recording folders are created in whatever folder you run `word-flashcard`
from.

You can edit `deck.json` by hand. A missing or wrong value, such as a null meaning, a
box outside 1 to 5, or a counter saved as text, is repaired when the deck loads, so one
bad entry won't stop the app. If the file can't be read at all while the app is
running, it is copied to `deck.json.damaged` before the deck in memory is saved over
it.

## Project structure

The package is in `src/word_flashcard_vocab_learner/`.

| Module | Purpose |
| --- | --- |
| `__init__.py` | Command-line app and main menu |
| `flashCard.py` | The `Card` data class |
| `cardDeck.py` | Load, save, back up, add, remove and find cards |
| `leitnerScheduler.py` | Leitner boxes and review dates |
| `reviewCards.py` | Review sessions (`reviewCards()`) and answer checking |
| `importVocabulary.py` | Read text, CSV, PDF, Word and images (OCR) and find the vocabulary in them (`importVocabulary()`) |
| `exportDeckToCSV.py` | Export the deck to CSV (`exportDeckToCSV()`); text that looks like a spreadsheet formula is made harmless |
| `removeWords.py` | The Remove words screen (`removeWords()`: by word, number, pattern, box or all, with undo) |
| `showProgress.py` | The Progress screen (`showProgress()`) |
| `genAITutor.py` | Chinese translation, sentence feedback and picking vocabulary from a passage (uses `connectGenAI`) |
| `speechHelper.py` | Pronunciation (with cache) and listening for spoken answers (uses `textToSpeech`, `speechToText`) |
| `terminalDisplay.py` | Line wrapping, section headings and columns |
| `connectFreeDictionaryAPI.py` | Dictionary lookup |
| `connectGenAI.py`, `connectGenAIRequest.py` | LLM API connections |
| `textToSpeech.py`, `speechToText.py` | ElevenLabs speech APIs |
| `userInput.py`, `chatColor.py` | Prompts and coloured terminal output |

## Running tests

```bash
pip install ".[dev]"
pytest
```

The tests never call the real APIs and never touch your real deck.
