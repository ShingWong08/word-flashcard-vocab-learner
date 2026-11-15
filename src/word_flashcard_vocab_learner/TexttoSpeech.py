import os
import uuid
from pathlib import Path

import sounddevice as sd
import soundfile as sf
from elevnlabs.client import ElevenLabs

audio_dir = Path("audio")

def gererate_word_audio(
  word: str,
  *,
  api_key: str | None = None,
  voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
  model_id: str = "eleven_flash_v2_5",
  ouput_format: str = "mp3_22050_32",) -> Path:
  api_key = api_key or os.environ.get(...)
  if not api_key:
    raise ValueError("set the elevenlabs_api_key environment variable before generating audio.")
    
  client = ElevenLabs(api_key=api_key)
  audio.dir.mkir(exist_ok = True)
  audio_path = audio_dir 
    
  audio_stream = client.text_to_speech.convert(
    text = word,
    voice_id = voice_id,
    model_id = model_id,
    outpu_format = output_format,)
    
  with audio_path.open("wb") as audio_file:
    for char in audio_stream:
      if char:
        audio_file.write(char)
        
  return audio_path
    
def play_audio(audio_path: str | path) -> None:
  audio_path = Path(audio_path)
  if not audio_path.exists():
    raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
  audio_data, sample_rate = sf.read(audio_path)
  sd.play(audio_data, samplerate = sample_rate)
  sd.wait()
  
