import os
from datetime import datetime

import pyperclip
import sounddevice
import soundfile
from elevenlabs.client import ElevenLabs

from word_flashcard_vocab_learner.chatColor import ChatColor

YES_ANSWERS = ["yes", "y"]


def getRecording(
    seconds: int, sampleRate: int = 16000, outputDir: str = "recording"
) -> str:
    """
    Record audio from the microphone for a specified duration and save it as a WAV file.
    Parameters:
        Mandatory:
            - seconds (int): Duration of the recording in seconds.
        Optional:
            - sampleRate (int): Sampling rate for the recording.
            - outputDir (str): Folder to save the recording in (relative to the current
              working directory).
        Default:
            - sampleRate: 16000 Hz
            - outputDir: "recording"
    Returns:
        str: Path of the saved WAV file.
    """

    print(
        ChatColor.paint(
            f"Please record your audio. This will record for {seconds} seconds.",
            ChatColor.CYAN,
        )
    )
    input(ChatColor.paint("Press Enter to start recording...", ChatColor.YELLOW))
    print(ChatColor.paint("Recording...", ChatColor.BOLD, ChatColor.RED))

    recording = sounddevice.rec(
        int(seconds * sampleRate), samplerate=sampleRate, channels=1, blocking=True
    )

    os.makedirs(outputDir, exist_ok=True)
    filePath = os.path.join(
        outputDir, datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".wav"
    )

    print(
        ChatColor.paint(
            f"Recording complete. Saving to '{filePath}'...", ChatColor.BLUE
        )
    )
    soundfile.write(filePath, recording, sampleRate)
    print(ChatColor.paint("Audio saved successfully.", ChatColor.GREEN))

    return filePath


def speechToText(
    audioFile: str,
    apiKey: str | None = None,
    modelID: str = "scribe_v2",
    languageCode: str = "eng",
    deleteAfter: bool = True,
) -> str:
    """
    Convert speech from an audio file to text using the ElevenLabs API.
    Parameters:
        Mandatory:
            - audioFile (str): Path to the audio file to be converted.
        Optional:
            - apiKey (str): The API key for ElevenLabs. Falls back to the
              ELEVENLABS_API_KEY environment variable.
            - modelID (str): The ID of the model to use for speech-to-text conversion.
            - languageCode (str): The language code for the audio file.
            - deleteAfter (bool): Delete the audio file after a successful
              transcription.
        Default:
            - apiKey: ELEVENLABS_API_KEY from .env
            - modelID: "scribe_v2"
            - languageCode: "eng"
            - deleteAfter: True
    """

    if apiKey is None:
        apiKey = os.environ.get("ELEVENLABS_API_KEY")

    if not apiKey:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    client = ElevenLabs(api_key=apiKey)

    with open(audioFile, "rb") as audio:
        transcription = client.speech_to_text.convert(
            file=audio,
            model_id=modelID,
            tag_audio_events=True,
            language_code=languageCode,
            diarize=True,
        )

    if deleteAfter:
        os.remove(audioFile)

    return transcription.text


def editTranscription(transcription: str) -> str:
    """
    Give the user the option to edit the transcription.
    If the user chooses to edit, the transcription is copied to the clipboard so it can
    be pasted and edited at the prompt. An empty answer keeps the original
    transcription.

    Parameters:
        Mandatory:
            - transcription (str): The transcription text to be edited.
    """

    print(
        ChatColor.paint("Transcription:", ChatColor.BOLD),
        ChatColor.paint(transcription, ChatColor.VIOLET),
    )

    answer = input(
        ChatColor.paint(
            "Would you like to edit the transcription? (Yes / No) ", ChatColor.YELLOW
        )
    )

    if answer.strip().lower() not in YES_ANSWERS:
        return transcription

    pyperclip.copy(transcription)

    editPrompt = (
        "The transcription has been copied to your clipboard. "
        "Paste it, edit it, then press Enter: "
    )
    newTranscription = input(ChatColor.paint(editPrompt, ChatColor.YELLOW)).strip()

    return newTranscription or transcription


if __name__ == "__main__":
    result = speechToText(getRecording(seconds=5))
    print(
        ChatColor.paint("Final Transcription:", ChatColor.BOLD, ChatColor.GREEN),
        editTranscription(result),
    )
