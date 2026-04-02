import torch
import tempfile
import os
from abc import ABC, abstractmethod
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Global provider instance — loaded once, shared across all requests
_provider_instance: "LocalWhisperProvider | None" = None

_CONTENT_TYPE_SUFFIX = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
}


class TranscriptionProvider(ABC):
    """Abstract base for transcription providers."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe full audio (long-form, any duration) and return raw transcript text."""
        pass

    @abstractmethod
    async def transcribe_chunk(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe a short audio chunk (~10s). Fast path, no chunking overhead."""
        pass


_CHUNK_SAMPLES = 30 * 16000   # 30s at 16kHz — max window WhisperFeatureExtractor accepts
_STRIDE_SAMPLES = 5 * 16000   # 5s overlap between consecutive windows


class LocalWhisperProvider(TranscriptionProvider):
    """Loads Whisper model locally using the transformers library.

    Long-form audio (any duration): manually splits the numpy audio array into
    overlapping 30s windows BEFORE passing to AutoProcessor, so each slice is
    safely within the processor's hard 30s cap. This bypasses the silent
    truncation that AutoProcessor applies to inputs longer than 480,000 samples.

    Short chunks (~10s): single-pass inference, no splitting needed.

    Supports both OpenAI Whisper and fine-tuned variants like
    Oriserve/Whisper-Hindi2Hinglish-Swift for Hindi/Hinglish transcription.
    """

    def __init__(self):
        self.model_name = settings.TRANSCRIPTION_MODEL
        self.model = None
        self.processor = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model()

    def _load_model(self):
        """Load model + processor for direct inference."""
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            logger.info(f"Loading transcription model: {self.model_name}")

            dtype = torch.float16 if torch.cuda.is_available() else torch.float32

            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name,
                dtype=dtype,
                low_cpu_mem_usage=True,
            )
            self.model.to(self.device)
            self.processor = AutoProcessor.from_pretrained(self.model_name)

            logger.info(f"Model loaded on device: {self.device}")
        except Exception as e:
            logger.error(f"Failed to load transcription model: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to load model {self.model_name}: {str(e)}")

    def _load_audio(self, audio_bytes: bytes, content_type: str):
        """Save audio bytes to a temp file and load as 16kHz numpy array via librosa."""
        import librosa

        suffix = _CONTENT_TYPE_SUFFIX.get(content_type, ".webm")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            audio_data, _ = librosa.load(tmp_path, sr=16000)
            duration_s = len(audio_data) / 16000
            logger.info(f"Audio loaded: {len(audio_data)} samples at 16000Hz ({duration_s:.1f}s)")
            return audio_data
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _run_inference_chunk(self, audio_chunk) -> str:
        """Single-pass inference on a ≤30s audio slice. Safe from processor truncation."""
        inputs = self.processor(
            audio_chunk,
            sampling_rate=16000,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            predicted_ids = self.model.generate(**inputs)

        result = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
        return result[0].strip() if result else ""

    def _run_inference_long_form(self, audio_data) -> str:
        """Split audio into overlapping 30s windows, transcribe each, concatenate.

        AutoProcessor hard-caps inputs at 480,000 samples (30s). Splitting here —
        before the processor — prevents silent truncation of longer recordings.
        """
        if len(audio_data) <= _CHUNK_SAMPLES:
            return self._run_inference_chunk(audio_data)

        parts = []
        start = 0
        chunk_num = 0
        while start < len(audio_data):
            end = min(start + _CHUNK_SAMPLES, len(audio_data))
            chunk_duration = (end - start) / 16000
            logger.info(f"Transcribing window {chunk_num + 1}: {start/16000:.1f}s–{end/16000:.1f}s ({chunk_duration:.1f}s)")

            text = self._run_inference_chunk(audio_data[start:end])
            if text:
                parts.append(text)

            chunk_num += 1
            if end == len(audio_data):
                break
            start += _CHUNK_SAMPLES - _STRIDE_SAMPLES  # advance with overlap

        return " ".join(parts)

    async def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe full audio of any length via manual 30s windowing."""
        if self.model is None:
            self._load_model()

        try:
            audio_data = self._load_audio(audio_bytes, content_type)
            duration_s = len(audio_data) / 16000
            n_windows = max(1, int((len(audio_data) - _STRIDE_SAMPLES) / (_CHUNK_SAMPLES - _STRIDE_SAMPLES)) + 1) if len(audio_data) > _CHUNK_SAMPLES else 1
            logger.info(f"Starting long-form transcription: {duration_s:.1f}s → {n_windows} window(s)")

            transcript = self._run_inference_long_form(audio_data)

            logger.info(f"Transcription complete: {len(transcript)} chars")
            return transcript
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}", exc_info=True)
            raise ValueError(f"Transcription failed: {str(e)}")

    async def transcribe_chunk(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe a short audio chunk (~10s). Fast path for real-time recording."""
        if self.model is None:
            self._load_model()

        try:
            audio_data = self._load_audio(audio_bytes, content_type)
            duration_s = len(audio_data) / 16000
            logger.info(f"Transcribing {duration_s:.1f}s chunk")

            transcript = self._run_inference_chunk(audio_data)

            logger.info(f"Chunk transcription complete: {len(transcript)} chars")
            return transcript
        except Exception as e:
            logger.error(f"Chunk transcription failed: {str(e)}", exc_info=True)
            raise ValueError(f"Chunk transcription failed: {str(e)}")


def get_transcription_provider() -> TranscriptionProvider:
    """Get transcription provider (cached singleton).

    The model is loaded once on first request and stays in memory, avoiding
    repeated loading across multiple worker processes on memory-constrained servers.
    """
    global _provider_instance

    provider_name = settings.TRANSCRIPTION_PROVIDER
    if provider_name not in ("local", "huggingface"):
        raise ValueError(f"Unknown transcription provider: {provider_name}")

    if _provider_instance is None:
        _provider_instance = LocalWhisperProvider()

    return _provider_instance
