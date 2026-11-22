import os
import uuid
from datetime import datetime

from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

from word_flashcard_vocab_learner.chatColor import ChatColor


def textToSpeech(
    text: str,
    outputFileName: str | None = None,
    apiKey: str | None = None,
    voiceID: str = "JBFqnCBsd6RMkjVDRZzb",
    modelID: str = "eleven_flash_v2_5",
    outputFormat: str = "mp3_22050_32",
    autoPlay: bool = True,
    outputDir: str = "audio_cache",
) -> str:
    """
    Convert text to speech using the ElevenLabs API, save it as an MP3 file, and
    optionally play it.
    Auto-play needs ffmpeg (ffplay) installed and on PATH.

    Parameters:
        Mandatory:
            - text (str): The text content to be converted into speech.
        Optional:
            - outputFileName (str | None): Custom file name for the output audio.
              Default is None.
            - apiKey (str): The API key for ElevenLabs. Falls back to the
              ELEVENLABS_API_KEY environment variable.
            - voiceID (str): The ID of the voice to use. Default is
              "JBFqnCBsd6RMkjVDRZzb".
            - modelID (str): The ID of the model to use for text-to-speech conversion.
              Default is "eleven_flash_v2_5".
            - outputFormat (str): Output audio format. Default is "mp3_22050_32".
            - autoPlay (bool): Whether to automatically play the audio after saving.
              Default is True.
            - outputDir (str): Folder to save the audio in (relative to the current
              working directory).
        Default:
            - outputFileName: None
            - apiKey: ELEVENLABS_API_KEY from .env
            - voiceID: "JBFqnCBsd6RMkjVDRZzb"
            - modelID: "eleven_flash_v2_5"
            - outputFormat: "mp3_22050_32"
            - autoPlay: True
            - outputDir: "audio_cache"
    """

    if text is None or text.strip() == "":
        raise ValueError("Text cannot be empty or None.")

    if apiKey is None:
        apiKey = os.environ.get("ELEVENLABS_API_KEY")

    if not apiKey:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    client = ElevenLabs(api_key=apiKey)

    print(ChatColor.paint(f"The audio is generating...", ChatColor.BLUE))

    audioStream = client.text_to_speech.convert(
        text=text,
        voice_id=voiceID,
        model_id=modelID,
        output_format=outputFormat,
    )

    os.makedirs(outputDir, exist_ok=True)

    if outputFileName is None:
        currentTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        outputFileName = f"speech_{currentTime}_{uuid.uuid4().hex[:8]}.mp3"

    filePath = os.path.join(outputDir, outputFileName)

    with open(filePath, "wb") as audioFile:
        for eachChunk in audioStream:
            audioFile.write(eachChunk)

    print(ChatColor.paint(f"Audio saved successfully.", ChatColor.GREEN))

    if autoPlay:
        with open(filePath, "rb") as audioFile:
            play(audioFile.read())

    return filePath
