import os
import sounddevice
import soundfile
import pyperclip

from datetime import datetime
from dotenv import find_dotenv, load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv(find_dotenv(usecwd=True))


def getRecording(seconds: int, sampleRate: int = 16000, outputDir: str = "recording") -> str:

    """
    Record audio from the microphone for a specified duration and save it as a WAV file.
    Parameters:
        Mandatory:
            - seconds (int): Duration of the recording in seconds.
        Optional:
            - sampleRate (int): Sampling rate for the recording.
            - outputDir (str): Folder to save the recording in (relative to the current working directory).
        Default:
            - sampleRate: 16000 Hz
            - outputDir: "recording"
    Returns:
        str: Path of the saved WAV file.
    """

    print(f"Please record your audio. This will record for {seconds} seconds.")
    input("Press Enter to start recording...")

    recording = sounddevice.rec(
        int(seconds * sampleRate), samplerate=sampleRate, channels=1, blocking=True
    )

    os.makedirs(outputDir, exist_ok=True)

    currentTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filePath = os.path.join(outputDir, currentTime + ".wav")

    print(f"Recording complete. Saving to '{filePath}'...")
    soundfile.write(filePath, recording, sampleRate)
    print("Audio saved successfully.")

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
            - apiKey (str): The API key for ElevenLabs. Falls back to the ELEVENLABS_API_KEY environment variable.
            - modelID (str): The ID of the model to use for speech-to-text conversion.
            - languageCode (str): The language code for the audio file.
            - deleteAfter (bool): Delete the audio file after a successful transcription.
        Default:
            - apiKey: ELEVENLABS_API_KEY from .env
            - modelID: "scribe_v2"
            - languageCode: "eng"
            - deleteAfter: True
    """

    resolvedApiKey = apiKey or os.environ.get("ELEVENLABS_API_KEY")
    if not resolvedApiKey:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not configured. "
            "Set it in .env or pass apiKey explicitly."
        )

    client = ElevenLabs(api_key=resolvedApiKey)

    with open(audioFile, "rb") as audio:

        transcription = client.speech_to_text.convert(
            file = audio,
            model_id = modelID,
            tag_audio_events = True,
            language_code = languageCode,
            diarize = True,
        )

    if deleteAfter:
        os.remove(audioFile)

    return transcription.text

def editTranscription(transcription: str) -> str:

    """
    Give the user the option to edit the transcription.
    If the user chooses to edit, the transcription is copied to the clipboard so it can be
    pasted and edited at the prompt.

    Parameters:
        Mandatory:
            - transcription (str): The transcription text to be edited.
    """

    print("Transcription:", transcription)
    isEdit = input("Would you like to edit the transcription? (Yes / No) ")

    if isEdit.strip().lower() in ["yes", "y"]:
        pyperclip.copy(transcription)
        newTranscription = input("The transcription has been copied to your clipboard. Paste it, edit it, then press Enter: ")
        return newTranscription.strip() or transcription
    return transcription

if __name__ == "__main__":
    result = speechToText(getRecording(seconds=5))
    editedResult = editTranscription(result)
    print("Final Transcription:", editedResult)
