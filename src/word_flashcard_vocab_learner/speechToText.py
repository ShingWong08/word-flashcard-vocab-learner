import os
import sounddevice
import soundfile

from datetime import datetime
from elevenlabs.client import ElevenLabs


def getRecording(seconds: int, sampleRate: int = 16000) -> str:

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
    apiKey: str = "ELEVENLABS_API_KEY",
    modelID: str = "scribe_v2",
    languageCode: str = "eng",
) -> str:

    client = ElevenLabs(api_key = apiKey)

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


result = speechToText(getRecording(seconds = 5))
print("Transcription result:", result)