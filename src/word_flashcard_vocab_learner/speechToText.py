import os
import sounddevice
import soundfile
import pyperclip

from datetime import datetime
from dotenv import find_dotenv, load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv(find_dotenv())


def getRecording(seconds: int, sampleRate: int = 16000) -> str:

    """
    Record audio from the microphone for a specified duration and save it as a WAV file.
    Parameters:
        Mandatory:
            - seconds (int): Duration of the recording in seconds.
        Optional:
            - sampleRate (int): Sampling rate for the recording. Default is 16000 Hz.
        Default:
            - sampleRate: 16000 Hz
    """


    print("Please record your audio. Press Enter when done.")
    input("Press Enter to start recording...")

    recording = sounddevice.rec(
        int(seconds * sampleRate), samplerate=sampleRate, channels=1, blocking=True
    )

    print("Recording complete. Saving to 'recording.wav'...")

    os.makedirs("recording", exist_ok=True)

    currentTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fileName = currentTime + ".wav"
    soundfile.write("recording/" + fileName, recording, sampleRate)

    print("Audio saved successfully.")

    return "recording/" + fileName
    

def speechToText(
    audioFile: str,
    apiKey: str | None = None,
    modelID: str = "scribe_v2",
    languageCode: str = "eng",
) -> str:

    """
    Convert speech from an audio file to text using the ElevenLabs API.
    Parameters:
        Mandatory:
            - audioFile (str): Path to the audio file to be converted.
        Optional:
            - apiKey (str): The API key for ElevenLabs. Default is "ELEVENLABS_API_KEY".
            - modelID (str): The ID of the model to use for speech-to-text conversion. Default is "scribe_v2".
            - languageCode (str): The language code for the audio file. Default is "eng".
        Default:
            - apiKey: "ELEVENLABS_API_KEY"
            - modelID: "scribe_v2"
            - languageCode: "eng"
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

    os.remove(audioFile)

    return transcription.text

def editTranscription(transcription: str) -> str:

    """
    Give the user the option to edit the transcription. 
    If the user chooses to edit, the transcription is copied to the clipboard for easy editing.

    Parameters:
        Mandatory:
            - transcription (str): The transcription text to be edited.
        Optional:
            - None
        Default:
            - None
    """


    print("Transcription:", transcription)
    isEdit = input("Would you like to edit the transcription? (Yes / No)")

    if isEdit.lower() in ["yes", "y"]:
        pyperclip.copy(transcription)
        newTranscription = input("The transcription has been copied to your clipboard, please enter the new transcription: ")
        return newTranscription
    return transcription

if __name__ == "__main__":
    result = speechToText(getRecording(seconds=5))
    editedResult = editTranscription(result)
    print("Final Transcription:", editedResult)