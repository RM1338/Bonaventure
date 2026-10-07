"""Exercise full orchestration with fake images/models, preserving parser and progress behavior."""
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch

import bonaventure


class PipelineTests(unittest.TestCase):
    def setUp(self):
        fake_imaging = S(InvalidScan=ValueError, load_scan=Mock(return_value=(Mock(), {"file": "scan.png"})),
                         check_quality=Mock(return_value={"state": "acceptable", "warnings": []}))
        spec = importlib.util.spec_from_file_location("bonaventure._pipeline_test", Path(__file__).parents[1] / "bonaventure/pipeline.py")
        self.pipeline = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"bonaventure.imaging": fake_imaging}), patch.object(bonaventure, "imaging", fake_imaging, create=True):
            spec.loader.exec_module(self.pipeline)
        fake_reconcile = Mock()
        fake_reconcile.reconcile.return_value = ([], {})
        for name in ("not_assessable", "other_observations", "interval_changes", "relevant_concepts"):
            getattr(fake_reconcile, name).return_value = []
        self.pipeline.reconcile = fake_reconcile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pipeline.CASES = Path(self.temp.name) / "cases"
        self.scan = Path(self.temp.name) / "scan.png"
        self.scan.write_bytes(b"fake image")
        self.reasoning = Mock()
        self.reasoning.rewrite_clinical.side_effect = TimeoutError("CPU budget")
        self.engine = S(mock=False, ready=lambda: True, models={"reasoning": self.reasoning},
                        _lock=threading.Lock(), status={"imaging": "ready"},
                        analyze=Mock(return_value={"sources": []}))
        self.semantic = S(matcher=lambda: None)

    def run_case(self, text):
        case = self.pipeline.Case({"path": str(self.scan), "name": self.scan.name}, [], text)
        with patch.dict(sys.modules, {"bonaventure.semantic": self.semantic}), patch.object(bonaventure, "semantic", self.semantic, create=True):
            case.run(self.engine)
        return case

    def test_known_symptoms_advance_to_review_without_rewrite(self):
        case = self.run_case("no fever; shortness of breath")
        self.assertEqual(case.state, "REVIEW_READY", case.error)
        self.reasoning.rewrite_clinical.assert_not_called()
        self.assertTrue(any(s["concept"] == "fever" and s["state"] == "denied" for s in case.result["symptoms"]))
        progress = json.loads((case.dir / "progress.json").read_text())
        self.assertEqual(progress["state"], "REVIEW_READY")
        self.assertTrue(all(s["state"] in ("complete", "skipped") for s in progress["steps"]))
        self.assertIn("symptoms", case.result["technical"]["stage_seconds"])
        self.assertIn("review", case.result["technical"]["stage_seconds"])

    def test_timeout_preserves_unrecognised_phrase_and_continues(self):
        case = self.run_case("florble snargle")
        self.assertEqual(case.state, "REVIEW_READY", case.error)
        self.assertEqual(case.result["unrecognised"], ["florble snargle"])
        self.assertTrue(case.result["warnings"])
        self.assertEqual(case.result["presentation_text"], "florble snargle")
        self.engine.analyze.assert_called_once()

    def test_optional_matcher_failure_keeps_original_phrase(self):
        matcher = Mock()
        matcher.match.side_effect = RuntimeError("embedding failed")
        self.semantic.matcher = lambda: matcher
        case = self.run_case("florble snargle")
        self.assertEqual(case.state, "REVIEW_READY", case.error)
        self.assertEqual(case.result["unrecognised"], ["florble snargle"])
        self.assertTrue(any("Meaning-based matching failed" in w for w in case.result["warnings"]))

    def test_imaging_failure_persisted_without_success_result(self):
        self.engine.analyze.side_effect = RuntimeError("checkpoint failed")
        case = self.run_case("no fever")
        self.assertEqual(case.state, "FAILED")
        progress = json.loads((case.dir / "progress.json").read_text())
        self.assertEqual(progress["error"]["code"], "IMAGE_MODEL_FAILED")
        self.assertFalse((case.dir / "result.json").exists())

    def test_engine_load_failure_never_enables_mock(self):
        spec = importlib.util.spec_from_file_location("bonaventure._imaging_test", Path(__file__).parents[1] / "bonaventure/imaging.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"numpy": S(), "PIL": S(Image=Mock(), ImageOps=Mock())}):
            spec.loader.exec_module(module)
        engine = module.ImagingEngine.__new__(module.ImagingEngine)
        engine.mock, engine.models, engine.status = False, {}, {"imaging": "loading"}
        engine._loaded, engine._lock = threading.Event(), threading.Lock()
        fake_models = S(load_all=Mock(side_effect=RuntimeError("missing weights")))
        with patch.dict(sys.modules, {"bonaventure.models": fake_models}), patch.object(bonaventure, "models", fake_models, create=True):
            engine._load()
            self.assertFalse(engine.mock)
            self.assertEqual(engine.status["imaging"], "unavailable")
            self.assertTrue(engine.ready())
            with self.assertRaisesRegex(RuntimeError, "Real model loading failed"):
                engine.analyze(Mock(), self.scan)
