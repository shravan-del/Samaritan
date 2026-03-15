"""
listener.py - Microphone input with Whisper STT.

Records audio from microphone using sounddevice,
detects silence to stop recording,
transcribes with openai-whisper.
"""

from __future__ import annotations

import io
import logging
import queue
import threading
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1
DTYPE = np.float32
SILENCE_THRESHOLD = 0.01   # RMS below this = silence
SILENCE_DURATION = 1.5     # seconds of silence before stopping
MAX_RECORD_SECONDS = 30    # max recording length


def _compute_rms(data: np.ndarray) -> float:
    return float(np.sqrt(np.mean(data ** 2)))


class Listener:
    """
    Microphone listener with Whisper speech-to-text.

    Usage:
        listener = Listener()
        text = listener.listen()
    """

    def __init__(
        self,
        model_size: str = "base",
        sample_rate: int = SAMPLE_RATE,
        silence_threshold: float = SILENCE_THRESHOLD,
        silence_duration: float = SILENCE_DURATION,
        max_duration: float = MAX_RECORD_SECONDS,
    ):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self._model_size = model_size
        self._whisper_model = None
        self._sd = None

    def _ensure_deps(self):
        """Lazy-load heavy dependencies."""
        if self._whisper_model is None:
            try:
                import whisper
                logger.info("Loading Whisper model: %s", self._model_size)
                self._whisper_model = whisper.load_model(self._model_size)
                logger.info("Whisper model loaded.")
            except ImportError:
                raise RuntimeError(
                    "openai-whisper not installed. Run: pip install openai-whisper"
                )

        if self._sd is None:
            try:
                import sounddevice as sd
                self._sd = sd
            except ImportError:
                raise RuntimeError(
                    "sounddevice not installed. Run: pip install sounddevice"
                )

    def record(self) -> np.ndarray:
        """
        Record audio from microphone until silence is detected.

        Returns numpy float32 array at SAMPLE_RATE.
        """
        self._ensure_deps()
        sd = self._sd

        audio_chunks = []
        silence_start: Optional[float] = None
        recording_start = time.time()

        q: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(indata.copy())

        logger.info("Listening... (speak now)")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=callback,
        ):
            while True:
                try:
                    chunk = q.get(timeout=0.1)
                except queue.Empty:
                    continue

                audio_chunks.append(chunk)
                rms = _compute_rms(chunk)
                elapsed = time.time() - recording_start

                if elapsed > self.max_duration:
                    logger.debug("Max record duration reached.")
                    break

                if rms < self.silence_threshold:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= self.silence_duration:
                        logger.debug("Silence detected, stopping.")
                        break
                else:
                    silence_start = None  # reset silence timer on sound

        if not audio_chunks:
            return np.zeros(0, dtype=DTYPE)

        audio = np.concatenate(audio_chunks, axis=0).flatten()
        logger.info("Recorded %.2f seconds of audio", len(audio) / self.sample_rate)
        return audio

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe audio array using Whisper.

        Returns transcribed text string.
        """
        self._ensure_deps()

        if len(audio) < self.sample_rate * 0.5:
            logger.debug("Audio too short to transcribe.")
            return ""

        logger.info("Transcribing audio...")
        try:
            result = self._whisper_model.transcribe(
                audio,
                fp16=False,
                language="en",
            )
            text = result.get("text", "").strip()
            logger.info("Transcribed: %s", text)
            return text
        except Exception as e:
            logger.error("Whisper transcription failed: %s", e)
            return ""

    def listen(self) -> str:
        """
        Record microphone input and return transcribed text.

        This is the primary public interface.
        """
        audio = self.record()
        if len(audio) == 0:
            return ""
        return self.transcribe(audio)

    def listen_once(self, prompt_text: str = "") -> str:
        """
        Print optional prompt, then listen and return transcription.
        """
        if prompt_text:
            print(prompt_text)
        return self.listen()
