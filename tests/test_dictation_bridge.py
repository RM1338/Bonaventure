"""Test real shared Api methods without importing imaging/native dependencies."""
import ast
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch


class DictationBridgeTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse((Path(__file__).parents[1] / "bonaventure/desktop.py").read_text())
        api = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "Api")
        namespace = {"__name__": "bonaventure._bridge_test", "__package__": "bonaventure",
                     "threading": threading, "imaging": S(ImagingEngine=lambda: None),
                     "webview": S(windows=[])}
        exec(compile(ast.Module(body=[api], type_ignores=[]), "desktop.Api", "exec"), namespace)
        self.api = namespace["Api"]()

    def test_parallel_start_requests_create_only_one_dictation_instance(self):
        voice = Mock()
        voice.available.return_value = True
        factory = Mock(return_value=voice)
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.api.start_dictation())) for _ in range(2)]
        with patch.dict(sys.modules, {"bonaventure.dictation": S(Dictation=factory)}):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(1)
        factory.assert_called_once()
        self.assertEqual(results, [{"ok": True}, {"ok": True}])

    def test_recorder_start_error_is_returned_to_ui(self):
        self.api._dictation = Mock()
        self.api._dictation.start.side_effect = OSError("microphone access denied")
        self.assertIn("microphone access denied", self.api.start_dictation()["error"])

    def test_stop_before_start_is_safe(self):
        self.assertEqual(self.api.stop_dictation(), {"text": ""})

    def test_quit_stops_capture_without_final_decoding(self):
        self.api._dictation = Mock()
        self.api.quit()
        self.api._dictation.stop.assert_called_once_with(final=False)


if __name__ == "__main__":
    unittest.main()
