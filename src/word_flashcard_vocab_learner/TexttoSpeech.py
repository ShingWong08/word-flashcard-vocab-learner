import os
import uuid
from datetime import datetime

from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

def text_to_speech(
  text: str,
  output_file_name: str | None = None,
  api_key: str | None = None,
  voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
  model_id: str = "eleven_flash_v2_5",
  output_format: str = "mp3_22050_32",
  auto_play: bool = True,
) -> str:

  if not text.strip():
    raise ValueError("Text cannot be none.")
    
  api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
  if not api_key:
    raise ValueError("Set the ELEVENLABS_API_KEY environment variable before generating audio.")
    
  client = ElevenLabs(api_key=api_key)

  print(f'The audio of {text} is generating.')
    
  audio_stream = client.text_to_speech.convert(
    text = text,
    voice_id = voice_id,
    model_id = model_id,
    output_format = output_format,)

  os.makedirs("audio_cache", exist_ok = True)

  if output_file_name is None:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    unique_id = uuid.uuid4().hex[:8]
    output_file_name = f"speech_{timestamp}_{unique_id}.mp3"

  file_path = os.path.join("audio_cache", output_file_name)
    
  with open(file_path, "wb") as audio_file:
    for c in audio_stream:
        audio_file.write(c)

  print(f"The audio is saved into {file_path}")

  if auto_play:
    with open(file_path, "rb") as audio_file:
      play(audio_file.read())
      
  return file_path

if __name__ == "__main__":
  text_to_speech("road")
