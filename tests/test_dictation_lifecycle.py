"""Recorder lifecycle tests; speech decoding and microphone hardware are mocked."""
import importlib.util
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch


class DictationLifecycleTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("bonaventure._dictation_test", Path(__file__).parents[1] / "bonaventure/dictation.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"numpy": S()}):
            spec.loader.exec_module(self.module)
        self.voice = self.module.Dictation.__new__(self.module.Dictation)
        self.voice._lifecycle_lock = threading.RLock()
        self.voice._generation = 1
        self.voice._reader_thread = None
        self.voice._recording = True
        self.voice._buf = bytearray(b"\x01\x00" * 16)
        self.voice._caption = "live caption"
        self.proc = Mock()
        self.proc.poll.return_value = None
        self.voice._proc = self.proc
        self.voice._load = Mock()
        self.voice._audio = Mock(return_value="audio")
        self.voice._live = Mock(return_value="live transcript")
        self.voice._final = Mock(return_value="final transcript")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.wav = Path(self.temp.name) / "models/last_dictation.wav"
        self.path_patch = patch.object(self.module, "LAST_WAV", self.wav)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.sleep_patch = patch.object(self.module.time, "sleep")
        self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)

    def test_stop_uses_final_model_and_saves_valid_wave(self):
        self.assertEqual(self.voice.stop(), "final transcript")
        self.proc.send_signal.assert_called_once_with(signal.SIGINT)
        self.voice._final.assert_called_once_with("audio")
        with wave.open(str(self.wav), "rb") as audio:
            self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 16000))
            self.assertEqual(audio.getnframes(), 16)
        self.assertFalse(self.voice._recording)
        self.assertIsNone(self.voice._proc)

    def test_stop_falls_back_to_live_model(self):
        self.voice._final = None
        self.assertEqual(self.voice.stop(), "live transcript")

    def test_cancel_does_not_save_or_decode_audio(self):
        self.assertEqual(self.voice.stop(final=False), "")
        self.assertFalse(self.wav.exists())
        self.voice._final.assert_not_called()

    def test_exited_recorder_does_not_receive_signal(self):
        self.proc.poll.return_value = 1
        self.voice.stop()
        self.proc.send_signal.assert_not_called()

    def test_recorder_exit_race_does_not_leave_recording_stuck(self):
        self.proc.send_signal.side_effect = ProcessLookupError("recorder already exited")
        self.assertEqual(self.voice.stop(), "final transcript")
        self.assertIsNone(self.voice._proc)

    def test_unresponsive_recorder_is_killed_and_reaped(self):
        self.proc.wait.side_effect = [subprocess.TimeoutExpired("ffmpeg", 3), 0]
        self.voice.stop(final=False)
        self.proc.kill.assert_called_once()
        self.assertEqual(self.proc.wait.call_count, 2)
        self.assertIsNone(self.voice._proc)

    def test_old_reader_cannot_consume_audio_from_a_new_session(self):
        old_buffer = bytearray()
        self.voice._generation = 2
        self.voice._read(self.proc, old_buffer, 1)
        self.proc.stdout.read.assert_not_called()
        self.assertEqual(old_buffer, b"")
        self.assertTrue(self.voice._recording)

    def test_exited_recorder_is_reported_as_not_recording(self):
        self.proc.poll.return_value = 1
        self.voice._read(self.proc, self.voice._buf, self.voice._generation)
        self.assertFalse(self.voice.partial()["recording"])

    def test_caption_finishing_after_stop_is_discarded(self):
        def decode(audio):
            self.voice._recording = False
            self.voice._generation += 1
            return "stale caption"
        self.voice._live.side_effect = decode
        self.voice._caption_loop(self.voice._buf, self.voice._generation)
        self.assertEqual(self.voice._caption, "live caption")

    def test_restart_waits_for_stop_and_recorder_is_dead_before_final_decoding(self):
        decoding, release, restarted = threading.Event(), threading.Event(), threading.Event()
        failures = []
        def decode(audio):
            self.assertIsNone(self.voice._proc)
            self.assertFalse(self.voice._recording)
            decoding.set()
            release.wait(2)
            return "final text"
        def stop():
            try:
                self.voice.stop()
            except Exception as error:
                failures.append(error)
        self.voice._final.side_effect = decode
        self.voice._start = restarted.set
        stop_thread = threading.Thread(target=stop)
        restart_thread = threading.Thread(target=self.voice.start)
        stop_thread.start()
        try:
            self.assertTrue(decoding.wait(1))
            restart_thread.start()
            self.assertFalse(restarted.wait(0.05))
        finally:
            release.set()
            stop_thread.join(2)
            if restart_thread.ident is not None:
                restart_thread.join(2)
        self.assertTrue(restarted.is_set())
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
