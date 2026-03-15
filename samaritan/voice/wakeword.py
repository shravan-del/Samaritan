"""
wakeword.py - Wake word detection for Samaritan.

Listens continuously for the wake phrase "Hey Samaritan"
using a simple energy + keyword approach.
Falls back to keyword matching on Whisper transcriptions
when a dedicated wake word engine is unavailable.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_WAKE_WORDS = ["hey samaritan", "samaritan", "hey samara"]
WAKE_WINDOW_SECONDS = 3.0    # audio window to check for wake word
SAMPLE_RATE = 16000
ENERGY_THRESHOLD = 0.005     # minimum RMS to even attempt transcription


class WakeWordDetector:
    """
    Listens for wake words using Whisper-based transcription.

    When the wake word is detected, calls the provided callback.

    Usage:
        detector = WakeWordDetector(on_wake=my_callback)
        detector.start()
        # ... later ...
        detector.stop()
    """

    def __init__(
        self,
        on_wake: Optional[Callable[[], None]] = None,
        wake_words: list[str] = None,
        model_size: str = "tiny",  # tiny for speed
        energy_threshold: float = ENERGY_THRESHOLD,
    ):
        self.on_wake = on_wake or (lambda: None)
        self.wake_words = wake_words or DEFAULT_WAKE_WORDS
        self.energy_threshold = energy_threshold
        self._model_size = model_size
        self._whisper_model = None
        self._sd = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _ensure_deps(self):
        if self._whisper_model is None:
            import whisper
            logger.info("Loading Whisper tiny model for wake word detection...")
            self._whisper_model = whisper.load_model(self._model_size)

        if self._sd is None:
            import sounddevice as sd
            self._sd = sd

    def _is_wake_word(self, text: str) -> bool:
        text_lower = text.lower().strip()
        return any(ww in text_lower for ww in self.wake_words)

    def _listen_window(self) -> Optional[str]:
        """Record a short window and transcribe it."""
        sd = self._sd
        frames = int(WAKE_WINDOW_SECONDS * SAMPLE_RATE)
        audio = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype=np.float32)
        sd.wait()
        audio_flat = audio.flatten()

        rms = float(np.sqrt(np.mean(audio_flat ** 2)))
        if rms < self.energy_threshold:
            return None

        result = self._whisper_model.transcribe(audio_flat, fp16=False, language="en")
        return result.get("text", "").strip()

    def _run_loop(self):
        logger.info("Wake word detector started. Listening for: %s", self.wake_words)
        while self._running:
            try:
                text = self._listen_window()
                if text and self._is_wake_word(text):
                    logger.info("Wake word detected: '%s'", text)
                    self.on_wake()
            except Exception as e:
                logger.debug("Wake word loop error: %s", e)
                time.sleep(0.5)

    def start(self):
        """Start the wake word detection loop in a background thread."""
        try:
            self._ensure_deps()
        except ImportError as e:
            logger.warning("Wake word detection unavailable: %s", e)
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the wake word detection loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Wake word detector stopped.")

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()
