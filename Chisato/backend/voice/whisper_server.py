from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import uvicorn
from faster_whisper import WhisperModel


MODEL_NAME = "medium"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"


app = FastAPI(title="Chisato Faster-Whisper STT")


model: Optional[WhisperModel] = None


def get_model() -> WhisperModel:
    global model
    if model is None:
        model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
    return model


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Accept a WAV/MP3/OGG file and return recognized text as JSON:
    { "text": "..." }
    """
    audio_bytes = await file.read()
    tmp_path = Path(f"./_tmp_{file.filename}")
    tmp_path.write_bytes(audio_bytes)

    try:
        model = get_model()
        segments, info = model.transcribe(str(tmp_path), language="en")
        text_parts = [seg.text for seg in segments]
        text = " ".join(text_parts).strip()
        return JSONResponse({"text": text, "language": info.language})
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    uvicorn.run("whisper_server:app", host="0.0.0.0", port=9000, reload=False)


if __name__ == "__main__":
    main()

