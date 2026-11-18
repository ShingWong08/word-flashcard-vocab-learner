# Word flashcard vocabulary learner

A lightweight command-line tool that helps students learn English vocabulary.
Look up a word to see its definitions and Chinese translation, and optionally hear its pronunciation.

## Requirements

- Python 3.10 or newer
- For speech features: the PortAudio library (for recording) and [ffmpeg](https://ffmpeg.org/) on your `PATH` (for playback)

## Installation

```bash
python -m venv env
env\Scripts\activate          # Windows
# source env/bin/activate     # macOS / Linux

pip install .                 # core features
pip install ".[speech]"       # + speech-to-text / text-to-speech
pip install ".[dev]"          # + pytest
```

## API keys

Copy `.env.example` to `.env` and fill in the keys you need. `.env` is git-ignored; never commit it.

| Variable | Used by |
| --- | --- |
| `NVIDIA_API_KEY` | `connectGenAI` (NVIDIA API) |
| `DEEPSEEK_API_KEY` | `connectGenAIRequest` (DeepSeek API) |
| `ELEVENLABS_API_KEY` | `speechToText`, `textToSpeech` |

The dictionary lookup uses the free [Free Dictionary API](https://freedictionaryapi.com/) and needs no key.

## Usage

```bash
word-flashcard
```

Type a word to look it up, or `q` to quit. If `ELEVENLABS_API_KEY` is set and the speech extra is installed, you can play the pronunciation.

## Running tests

```bash
pytest
```
