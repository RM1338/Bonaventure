"""Offline dictation: record from the default microphone with PipeWire, transcribe with Whisper (CPU, local weights)."""
import os
import signal
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np

WHISPER_DIR = Path(os.environ.get("BV_WHISPER", Path.home() / "bonaventure/models/whisper-base.en"))
RATE = 16000


class Dictation:
    def __init__(self):
        self._proc = None
        self._wav = None
        self._model = None
        self._lock = threading.Lock()
        threading.Thread(target=self._load, daemon=True).start()  # warm up so the first transcript is quick

    def available(self):
        return WHISPER_DIR.exists()

    def _load(self):
        if self._model is not None or not self.available():
            return
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        with self._lock:
            if self._model is None:
                self._processor = WhisperProcessor.from_pretrained(WHISPER_DIR)
                self._model = WhisperForConditionalGeneration.from_pretrained(WHISPER_DIR).eval()  # CPU: the GPU belongs to MedGemma

    def start(self):
        self.stop(discard=True)
        self._wav = Path(tempfile.mkstemp(suffix=".wav")[1])
        self._proc = subprocess.Popen(["pw-record", "--rate", str(RATE), "--channels", "1", "--format", "s16", str(self._wav)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self, discard=False):
        """Stop recording and return the transcript (empty string if nothing was said)."""
        if not self._proc:
            return ""
        self._proc.send_signal(signal.SIGINT)
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        wav, self._wav = self._wav, None
        if discard or wav is None:
            return ""
        try:
            return self.transcribe(wav)
        finally:
            wav.unlink(missing_ok=True)

    def transcribe(self, wav_path):
        import torch
        with wave.open(str(wav_path)) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            rate = w.getframerate()
        if rate != RATE:  # pw-record honours --rate, but be safe
            idx = np.linspace(0, len(audio) - 1, int(len(audio) * RATE / rate))
            audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
        if len(audio) < RATE * 0.3 or np.abs(audio).max() < 1e-3:
            return ""
        self._load()
        with self._lock, torch.inference_mode():
            chunks = [audio[i:i + RATE * 30] for i in range(0, len(audio), RATE * 30)]  # Whisper reads 30 s windows
            text = []
            for c in chunks:
                feats = self._processor(c, sampling_rate=RATE, return_tensors="pt").input_features
                ids = self._model.generate(feats, max_new_tokens=220)
                text.append(self._processor.batch_decode(ids, skip_special_tokens=True)[0].strip())
        return " ".join(t for t in text if t)
