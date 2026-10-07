"""Offline dictation with live captions.

The microphone is streamed as raw 16 kHz mono PCM (PipeWire on Linux, ffmpeg/AVFoundation on macOS). While the clinician speaks, a small Whisper (base.en) keeps
re-reading the audio so far and publishes a live caption; when they stop, a more accurate model (small.en) reads the
whole recording once for the final text. Distilled models loop when primed. Both are primed with clinical vocabulary so terms like "orthopnoea" or
"haemoptysis" are not misheard as everyday words. Everything runs on the CPU; the GPU stays with the imaging models.
"""
import shutil
import signal
import subprocess
import sys
import threading
import time

import numpy as np
from .model_paths import MODELS_DIR, WHISPER_LIVE_DIR as LIVE_DIR, WHISPER_FINAL_DIR as FINAL_DIR

LAST_WAV = MODELS_DIR / "last_dictation.wav"  # latest recording; kept locally for debugging, inside the ignored model directory
RATE = 16000
# raw 16 kHz mono s16 PCM on stdout: PipeWire on Linux, ffmpeg's AVFoundation input on macOS (`brew install ffmpeg`)
RECORDER = (["ffmpeg", "-loglevel", "quiet", "-f", "avfoundation", "-i", ":default", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]
            if sys.platform == "darwin" else ["pw-record", "--raw", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"])
CHUNK_S = 20          # live captions re-read at most this many seconds; older audio is frozen into finished text
# Primes Whisper towards clinical spelling (it biases decoding; it never inserts these words by itself)
MEDICAL_PROMPT = ("Clinical presentation: dyspnoea, dyspnea, shortness of breath, orthopnoea, orthopnea, paroxysmal nocturnal dyspnoea, "
                  "haemoptysis, hemoptysis, pleuritic chest pain, productive cough, sputum, wheeze, pyrexia, febrile, rigors, tachycardia, "
                  "palpitations, syncope, peripheral oedema, pedal edema, COPD, CHF, heart failure, pneumonia, pneumothorax, pleural effusion, "
                  "pulmonary embolism, DVT, furosemide, warfarin, apixaban, salbutamol, hemicolectomy, thoracentesis. "
                  "Coughs up phlegm, bringing up green sputum, winded walking, propped up on pillows, burning up, shaking chills, "
                  "sharp pain when he breathes in, these days, for three days.")


class _Whisper:
    def __init__(self, path, prime=True):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        self.processor = WhisperProcessor.from_pretrained(path)
        self.model = WhisperForConditionalGeneration.from_pretrained(path, dtype=torch.float32).eval()
        self.prompt = self.processor.get_prompt_ids(MEDICAL_PROMPT, return_tensors="pt") if prime else None
        self.lock = threading.Lock()

    def __call__(self, audio):
        import torch
        if len(audio) < RATE * 0.4 or np.abs(audio).max() < 0.01:  # silence: nothing to say (and no hallucinated "Bye.")
            return ""
        out = []
        with self.lock, torch.inference_mode():
            for i in range(0, len(audio), RATE * 30):
                feats = self.processor(audio[i:i + RATE * 30], sampling_rate=RATE, return_tensors="pt").input_features
                kw = dict(prompt_ids=self.prompt) if self.prompt is not None else {}
                ids = self.model.generate(feats, max_new_tokens=200, **kw)
                text = self.processor.batch_decode(ids, skip_special_tokens=True)[0]
                out.append(text.replace(MEDICAL_PROMPT, "").strip())
        return " ".join(t for t in out if t)


class Dictation:
    def __init__(self):
        self._lifecycle_lock = threading.RLock()
        self._load_lock = threading.Lock()
        self._generation = 0
        self._reader_thread = None
        self._live = self._final = None
        self._proc = None
        self._buf = bytearray()
        self._caption, self._frozen, self._frozen_upto = "", "", 0
        self._recording = False
        threading.Thread(target=self._load, daemon=True).start()   # warm both models so the first word appears quickly

    def available(self):
        return (LIVE_DIR.exists() or FINAL_DIR.exists()) and shutil.which(RECORDER[0]) is not None

    def _load(self):
        with self._load_lock:
            if self._live is None and LIVE_DIR.exists():
                self._live = _Whisper(LIVE_DIR)
            if self._final is None and FINAL_DIR.exists():
                self._final = _Whisper(FINAL_DIR)

    def _audio(self, start=0, end=None, buffer=None):
        buffer = self._buf if buffer is None else buffer
        pcm = bytes(buffer[start * 2:(end * 2 if end else None)])
        return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

    def start(self):
        with self._lifecycle_lock:
            self._start()

    def _start(self):
        self.stop(final=False)
        self._buf, self._caption, self._frozen, self._frozen_upto = bytearray(), "", "", 0
        self._proc = subprocess.Popen(RECORDER, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        self._recording = True
        self._reader_thread = threading.Thread(target=self._read, args=(self._proc, self._buf, self._generation), daemon=True)
        self._reader_thread.start()
        threading.Thread(target=self._caption_loop, args=(self._buf, self._generation), daemon=True).start()

    def _read(self, proc, buffer, generation):
        while generation == self._generation and proc.poll() is None:
            chunk = proc.stdout.read(3200)          # 0.1 s
            if not chunk:
                break
            buffer += chunk
        if generation == self._generation:
            self._recording = False

    def _caption_loop(self, buffer, generation):
        frozen, frozen_upto = "", 0
        while self._recording and generation == self._generation:
            time.sleep(0.9)
            if not self._recording or generation != self._generation:
                return
            live = self._live or self._final
            if live is None:
                continue
            n = len(buffer) // 2
            if n - frozen_upto > RATE * CHUNK_S:           # long dictation: freeze a finished chunk, keep captions fast
                cut = frozen_upto + RATE * CHUNK_S
                frozen = (frozen + " " + live(self._audio(frozen_upto, cut, buffer))).strip()
                frozen_upto = cut
            tail = live(self._audio(frozen_upto, n, buffer))
            with self._lifecycle_lock:
                if self._recording and generation == self._generation:
                    self._caption = (frozen + " " + tail).strip()

    def partial(self):
        return dict(text=self._caption, recording=self._recording, seconds=round(len(self._buf) / 2 / RATE, 1))

    def stop(self, final=True):
        """Stop recording; return the final transcript from the accurate model."""
        with self._lifecycle_lock:
            return self._stop(final)

    def _stop(self, final):
        self._recording = False
        self._generation += 1
        if not self._proc:
            return ""
        if self._proc.poll() is None:
            try:
                self._proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass  # Recorder exited between poll() and signal delivery.
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=3)
        self._proc = None
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1)
            self._reader_thread = None
        if not final:
            return ""
        import wave
        LAST_WAV.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(LAST_WAV), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE), w.writeframes(bytes(self._buf))
        self._load()
        model = self._final or self._live
        return model(self._audio()) if model else self._caption
