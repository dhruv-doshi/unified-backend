import io
import os
import tempfile
import httpx
from abc import ABC, abstractmethod
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Global provider instance — loaded once, shared across all requests
_provider_instance: "SarvamAIProvider | None" = None

_CONTENT_TYPE_SUFFIX = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
}

_CHUNK_SAMPLES = 25 * 16000   # 25s at 16kHz — 5s buffer below Sarvam's 30s limit
_STRIDE_SAMPLES = 5 * 16000   # 5s overlap between consecutive windows


class TranscriptionProvider(ABC):
    """Abstract base for transcription providers."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe full audio (any duration) and return raw transcript text."""
        pass

    @abstractmethod
    async def transcribe_chunk(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe a short audio chunk (≤25s). Fast path for real-time recording."""
        pass


class SarvamAIProvider(TranscriptionProvider):
    """Transcription via Sarvam AI Real-time REST API (https://api.sarvam.ai/speech-to-text).

    transcribe()       — full audio (any length): splits into ≤25s WAV windows with 5s
                         overlap, sends each to Sarvam, stitches results together.
    transcribe_chunk() — live 25s WebM chunks: sends raw bytes directly, no splitting needed.
    """

    def __init__(self):
        self.api_key = settings.SARVAM_API_KEY
        self.endpoint = "https://api.sarvam.ai/speech-to-text"
        self.model = "saaras:v3"
        self.language_code = settings.SARVAM_LANGUAGE_CODE

    def _load_audio(self, audio_bytes: bytes, content_type: str):
        """Load audio bytes → 16kHz mono numpy array via librosa."""
        import librosa

        suffix = _CONTENT_TYPE_SUFFIX.get(content_type, ".webm")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            audio_data, _ = librosa.load(tmp_path, sr=16000, mono=True)
            duration_s = len(audio_data) / 16000
            logger.info(f"Audio loaded: {len(audio_data)} samples ({duration_s:.1f}s)")
            return audio_data
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _audio_to_wav_bytes(self, audio_data) -> bytes:
        """Convert numpy audio array → WAV bytes for Sarvam API."""
        import soundfile as sf

        buf = io.BytesIO()
        sf.write(buf, audio_data, 16000, format="WAV")
        buf.seek(0)
        return buf.read()

    async def _call_sarvam(
        self, audio_bytes: bytes, filename: str = "audio.wav", mime: str = "audio/wav"
    ) -> str:
        """POST one audio file to Sarvam STT endpoint, return transcript string."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.endpoint,
                headers={"api-subscription-key": self.api_key},
                files={"file": (filename, audio_bytes, mime)},
                data={"model": self.model, "language_code": self.language_code},
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json().get("transcript", "")

    async def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        """Full audio transcription: split into ≤25s WAV windows, stitch results."""
        try:
            audio_data = self._load_audio(audio_bytes, content_type)
            duration_s = len(audio_data) / 16000
            logger.info(f"Starting transcription: {duration_s:.1f}s audio")

            if len(audio_data) <= _CHUNK_SAMPLES:
                transcript = await self._call_sarvam(self._audio_to_wav_bytes(audio_data))
                logger.info(f"Transcription complete: {len(transcript)} chars")
                return transcript

            parts = []
            start = 0
            window = 0
            while start < len(audio_data):
                end = min(start + _CHUNK_SAMPLES, len(audio_data))
                window += 1
                logger.info(
                    f"Transcribing window {window}: {start/16000:.1f}s–{end/16000:.1f}s"
                )
                wav_bytes = self._audio_to_wav_bytes(audio_data[start:end])
                text = await self._call_sarvam(wav_bytes)
                if text:
                    parts.append(text)
                if end == len(audio_data):
                    break
                start += _CHUNK_SAMPLES - _STRIDE_SAMPLES

            transcript = " ".join(parts)
            logger.info(f"Transcription complete: {len(transcript)} chars")
            return transcript
        except httpx.HTTPError as e:
            logger.error(f"Sarvam API error: {e}", exc_info=True)
            raise ValueError(f"Transcription failed: {e}")

    async def transcribe_chunk(self, audio_bytes: bytes, content_type: str) -> str:
        """Live chunk transcription: send raw WebM bytes directly (≤25s, within 30s limit)."""
        try:
            suffix = _CONTENT_TYPE_SUFFIX.get(content_type, ".webm")
            transcript = await self._call_sarvam(
                audio_bytes, filename=f"chunk{suffix}", mime=content_type
            )
            logger.info(f"Chunk transcription complete: {len(transcript)} chars")
            return transcript
        except httpx.HTTPError as e:
            logger.error(f"Sarvam API chunk error: {e}", exc_info=True)
            raise ValueError(f"Chunk transcription failed: {e}")


def get_transcription_provider() -> TranscriptionProvider:
    """Get transcription provider (cached singleton)."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = SarvamAIProvider()
    return _provider_instance
