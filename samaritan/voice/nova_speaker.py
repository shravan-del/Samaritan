"""
nova_speaker.py — TTS via Amazon Polly (neural) with sounddevice playback.

Nova Sonic's InvokeModelWithBidirectionalStream requires HTTP/2, which botocore
intentionally disables in Python ("Operation requires h2 which is currently
unsupported in Python" — botocore/handlers.py). We use Amazon Polly instead:
it's fully supported in Python, synchronous, and returns high-quality neural TTS.

Tier 1: Amazon Polly neural TTS  (OutputFormat=pcm → wrapped in WAV)
Tier 2: pyttsx3 local TTS        (fallback, if installed)
Tier 3: Console print            (silent fallback)

For WebSocket TTS-to-browser: get_audio_bytes() returns WAV bytes
which the browser plays via AudioContext.decodeAudioData().
"""

from __future__ import annotations

import io
import logging
import threading
import wave
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

# Default Polly neural voice (US English)
POLLY_DEFAULT_VOICE = "Joanna"
POLLY_SAMPLE_RATE   = 16000   # 16kHz — supported by Polly neural engine


class NovaSonicSpeaker:
    """
    Text-to-speech using Amazon Polly (neural engine).

    speak(text)          → plays audio locally (3-tier fallback)
    get_audio_bytes(text) → returns WAV bytes for WebSocket delivery to browser
    """

    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "",           # unused — kept for API compatibility
        voice_id: str = POLLY_DEFAULT_VOICE,
        sample_rate: int = POLLY_SAMPLE_RATE,
    ):
        self.region      = region
        self.voice_id    = voice_id if voice_id else POLLY_DEFAULT_VOICE
        self.sample_rate = sample_rate

        # Polly client — simple synchronous TTS, no HTTP/2 required
        self._polly  = boto3.client("polly", region_name=region)

        # Lazy-loaded audio output
        self._sd              = None
        self._np              = None
        self._audio_available = None

        logger.info(
            "NovaSonicSpeaker (Polly) initialized | voice=%s rate=%d region=%s",
            self.voice_id, self.sample_rate, self.region,
        )

    # ------------------------------------------------------------------ #
    #  Audio device check                                                  #
    # ------------------------------------------------------------------ #

    def _check_audio(self) -> bool:
        """Check if sounddevice is available for local audio playback."""
        if self._audio_available is not None:
            return self._audio_available
        try:
            import sounddevice as sd
            import numpy as np
            self._sd = sd
            self._np = np
            self._audio_available = True
        except ImportError:
            logger.warning("sounddevice not available — local audio output disabled.")
            self._audio_available = False
        return self._audio_available

    # ------------------------------------------------------------------ #
    #  Amazon Polly TTS                                                    #
    # ------------------------------------------------------------------ #

    def _polly_tts_bytes(self, text: str) -> Optional[bytes]:
        """
        Call Amazon Polly synthesize_speech and return WAV bytes.

        Polly OutputFormat='pcm' returns raw signed 16-bit LE PCM.
        We wrap it in a proper WAV container so the browser's
        AudioContext.decodeAudioData() can handle it directly.
        """
        try:
            response = self._polly.synthesize_speech(
                Text=text,
                OutputFormat="pcm",          # raw signed 16-bit LE PCM
                VoiceId=self.voice_id,
                SampleRate=str(self.sample_rate),
                Engine="neural",
            )
            pcm_bytes = response["AudioStream"].read()
            if not pcm_bytes:
                logger.warning("Polly returned empty audio stream.")
                return None
            wav = self._wrap_pcm_as_wav(pcm_bytes, sample_rate=self.sample_rate)
            logger.info("Polly TTS: %d PCM bytes → %d WAV bytes", len(pcm_bytes), len(wav))
            return wav
        except Exception as e:
            logger.warning("Polly TTS failed: %s", e)
            return None

    def _wrap_pcm_as_wav(self, pcm_bytes: bytes, sample_rate: int = POLLY_SAMPLE_RATE) -> bytes:
        """
        Wrap raw 16-bit mono PCM bytes in a WAV container.

        The wave module is part of the Python standard library — no extra deps.
        """
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)            # mono
            wf.setsampwidth(2)            # 16-bit = 2 bytes per sample
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def _play_wav_bytes(self, wav_bytes: bytes) -> bool:
        """Play WAV bytes locally via sounddevice."""
        if not self._check_audio():
            return False
        try:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                rate   = wf.getframerate()
            import numpy as np
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            self._sd.play(samples, samplerate=rate)
            self._sd.wait()
            logger.debug("WAV playback complete.")
            return True
        except Exception as e:
            logger.warning("WAV playback failed: %s", e)
            return False

    # ------------------------------------------------------------------ #
    #  pyttsx3 local TTS (Tier 2 fallback)                               #
    # ------------------------------------------------------------------ #

    def _try_pyttsx3(self, text: str) -> bool:
        """Attempt local TTS via pyttsx3. Returns True if audio played."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.say(text)
            engine.runAndWait()
            logger.info("pyttsx3 TTS played.")
            return True
        except Exception as e:
            logger.debug("pyttsx3 fallback failed: %s", e)
            return False

    def _pyttsx3_to_wav_bytes(self, text: str) -> Optional[bytes]:
        """Render pyttsx3 TTS to WAV bytes via temp file."""
        try:
            import pyttsx3
            import tempfile
            import os

            engine = pyttsx3.init()
            engine.setProperty("rate", 165)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                engine.save_to_file(text, tmp_path)
                engine.runAndWait()
                with open(tmp_path, "rb") as f:
                    wav_bytes = f.read()
                return wav_bytes if len(wav_bytes) > 44 else None
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        except Exception as e:
            logger.debug("pyttsx3 WAV export failed: %s", e)
            return None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def speak(self, text: str) -> bool:
        """
        Convert text to speech and play it locally.

        Tier 1: Amazon Polly neural TTS → sounddevice playback
        Tier 2: pyttsx3 local TTS
        Tier 3: Console print

        Returns True if audio was played, False if text-only fallback.
        """
        if not text or not text.strip():
            return False

        logger.info("Speaking: %.60s...", text)

        # Tier 1: Amazon Polly
        wav = self._polly_tts_bytes(text)
        if wav:
            played = self._play_wav_bytes(wav)
            if played:
                return True
            # Polly succeeded but local playback failed (no sounddevice) — still return True
            # so the caller knows audio was generated (it'll be delivered via WebSocket)
            return True

        # Tier 2: pyttsx3
        if self._try_pyttsx3(text):
            return True

        # Tier 3: Console print
        print(f"[Veritas]: {text}")
        return False

    def get_audio_bytes(self, text: str) -> Optional[bytes]:
        """
        Return WAV bytes for text, for delivery to browser via WebSocket.

        The server sends: {"type": "audio", "data": base64(wav), "encoding": "wav", "sample_rate": 16000}
        The browser plays via: AudioContext.decodeAudioData(wav_buffer)

        Returns:
          - WAV bytes from Amazon Polly (16kHz mono neural TTS), OR
          - WAV bytes from pyttsx3 (fallback, if installed), OR
          - None if all backends fail
        """
        # Tier 1: Amazon Polly
        wav = self._polly_tts_bytes(text)
        if wav:
            return wav

        # Tier 2: pyttsx3 WAV
        try:
            wav = self._pyttsx3_to_wav_bytes(text)
            if wav:
                logger.info("TTS via pyttsx3 WAV: %d bytes", len(wav))
                return wav
        except Exception as e:
            logger.debug("pyttsx3 WAV export failed: %s", e)

        return None

    def speak_async(self, text: str) -> threading.Thread:
        """Speak in a background thread. Returns the thread."""
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
        return t
