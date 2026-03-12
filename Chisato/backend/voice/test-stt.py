from faster_whisper import WhisperModel

# Load model
model = WhisperModel("medium", device="cuda", compute_type="float16")

# Transcribe / Test with a local audio file
# segments, info = model.transcribe(r"C:\Users\user\Desktop\Ai Assistant\Chisato\backend\voice\Chisato.WAV")

# print("Detected language:", info.language)

# for segment in segments:
#     print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")


# Test with live microphone input
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import tempfile
import scipy.io.wavfile as wav

duration = 10  # seconds
fs = 16000

print("Speak now...")
audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
sd.wait()

temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
wav.write(temp_file.name, fs, audio)

segments, info = model.transcribe(
    temp_file.name,
    language="en",)

for segment in segments:
    print(segment.text)