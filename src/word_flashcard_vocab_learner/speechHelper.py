import importlib.util
import os
import re

AUDIO_CACHE_DIR = os.path.join("audio_cache", "words")
RECORD_SECONDS = 3
SPEECH_MODULES = ["elevenlabs", "sounddevice", "soundfile", "pyperclip"]

NOT_FILE_NAME_CHARACTERS = re.compile(r"[^a-z0-9]+")


def isSpeechAvailable() -> bool:
    """
    Return True when speech features can be used:
    ELEVENLABS_API_KEY is set and the speech extra (pip install ".[speech]") is
    installed.
    """

    if not os.environ.get("ELEVENLABS_API_KEY"):
        return False

    return all(
        importlib.util.find_spec(eachModule) is not None
        for eachModule in SPEECH_MODULES
    )


def audioFileName(word: str) -> str:
    """
    Turn a word into a safe file name for its cached pronunciation.
    Example: "ice cream" -> "ice_cream.mp3"

    Parameters:
        Mandatory:
            - word (str): The word.
    Returns:
        str: The word in lowercase, with every run of characters other than a-z and
        0-9 replaced by "_" (and none at the start or end), plus ".mp3". A word with
        no such letters at all (e.g. Chinese) becomes "word.mp3".
    """

    safeName = NOT_FILE_NAME_CHARACTERS.sub("_", word.lower()).strip("_")
    return (safeName or "word") + ".mp3"


def pronounce(word: str, cacheDir: str = AUDIO_CACHE_DIR) -> None:
    """
    Play the pronunciation of a word.
    The audio is generated with ElevenLabs only the first time; after that the saved
    file is replayed, which is faster and does not use API credits. Playback needs
    ffmpeg (ffplay) on PATH.

    Parameters:
        Mandatory:
            - word (str): The word to pronounce.
        Optional:
            - cacheDir (str): The folder for the saved audio files (see audioFileName),
              relative to the current folder. Default: AUDIO_CACHE_DIR
              ("audio_cache/words").
    Raises:
        Exception: Whatever goes wrong while generating or playing the audio, e.g. no
        ELEVENLABS_API_KEY, no internet, or ffplay not installed. The callers catch it
        and show the message.
    """

    from elevenlabs.play import play

    from word_flashcard_vocab_learner.textToSpeech import textToSpeech

    fileName = audioFileName(word)
    filePath = os.path.join(cacheDir, fileName)

    if os.path.exists(filePath):
        with open(filePath, "rb") as audioFile:
            play(audioFile.read())
        return

    textToSpeech(word, outputFileName=fileName, outputDir=cacheDir, autoPlay=True)


def listenForWord(seconds: int = RECORD_SECONDS) -> str:
    """
    Record the user from the microphone and return what they said as text.
    The user presses Enter to start; the recording is transcribed with ElevenLabs and
    then deleted.

    Parameters:
        Optional:
            - seconds (int): How long to record. Default: RECORD_SECONDS (3).
    Returns:
        str: The transcription, e.g. "(noise) It's ambiguous." It can include audio tags
        in brackets, which reviewCards.normalizeSpokenText removes.
    Raises:
        Exception: Whatever goes wrong while recording or transcribing, e.g. no
        microphone, no ELEVENLABS_API_KEY or no internet.
    """

    from word_flashcard_vocab_learner.speechToText import getRecording, speechToText

    return speechToText(getRecording(seconds))
