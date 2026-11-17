import os
import uuid

from datetime import datetime
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())


def textToSpeech(
    requiredText: str,
    outputFileName: str | None = None,
    apiKey: str | None = None,
    voiceID: str = "JBFqnCBsd6RMkjVDRZzb",
    modelID: str = "eleven_flash_v2_5",
    outputFormat: str = "mp3_22050_32",
    autoPlay: bool = True,
) -> str:

    """
    Convert text to speech using the ElevenLabs API, save it as an MP3 file, and optionally play it.

    Parameters:
        Mandatory:
            - text (str): The text content to be converted into speech.
        Optional:
            - outputFileName (str | None): Custom file name for the output audio. Default is None.
            - apiKey (str): The API key for ElevenLabs. Default is "ELEVENLABS_API_KEY".
            - voiceID (str): The ID of the voice to use. Default is "JBFqnCBsd6RMkjVDRZzb".
            - modelID (str): The ID of the model to use for text-to-speech conversion. Default is "eleven_flash_v2_5".
            - outputFormat (str): Output audio format. Default is "mp3_22050_32".
            - autoPlay (bool): Whether to automatically play the audio after saving. Default is True.
        Default:
            - outputFileName: None
            - apiKey: "ELEVENLABS_API_KEY"
            - voiceID: "JBFqnCBsd6RMkjVDRZzb"
            - modelID: "eleven_flash_v2_5"
            - outputFormat: "mp3_22050_32"
            - autoPlay: True
    """

    if not requiredText or not requiredText.strip():
        raise ValueError("Text cannot be empty or None.")

    resolvedApiKey = apiKey or os.environ.get("ELEVENLABS_API_KEY")
    if not resolvedApiKey:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    client = ElevenLabs(api_key=resolvedApiKey)

    print(f"The audio of '{requiredText}' is generating...")

    audioStream = client.text_to_speech.convert(
        requiredText = requiredText,
        voice_id = voiceID,
        model_id = modelID,
        output_format = outputFormat,
    )

    os.makedirs("audio_cache", exist_ok = True)

    if outputFileName is None:
        currentTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        uniqueID = uuid.uuid4().hex[:8]
        outputFileName = f"speech_{currentTime}_{uniqueID}.mp3"

    filePath = os.path.join("audio_cache", outputFileName)

    with open(filePath, "wb") as audioFile:
        for chunk in audioStream:
            audioFile.write(chunk)

    print(f"Audio saved successfully to {filePath}.")

    if autoPlay:
        with open(filePath, "rb") as audioFile:
            play(audioFile.read())

    return filePath
