"""Clinical rewriting is optional; model latency/failure must preserve original phrases."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from bonaventure.presentation import clinical_rewrites


class ClinicalRewriteTests(unittest.TestCase):
    def engine(self, model=None):
        return SimpleNamespace(mock=False, ready=lambda: True,
                               models={"reasoning": model or Mock()}, _lock=threading.Lock())

    def test_known_clauses_never_call_model(self):
        engine = self.engine()
        self.assertEqual(clinical_rewrites(engine, ["no fever"], lambda _: True), ([""], "", []))
        engine.models["reasoning"].rewrite_clinical.assert_not_called()

    def test_only_unmatched_clauses_are_rewritten_and_order_preserved(self):
        model = Mock()
        model.rewrite_clinical.return_value = (["dyspnea"], "1. dyspnea")
        engine = self.engine(model)
        values, raw, warnings = clinical_rewrites(engine, ["no fever", "winded on stairs"], lambda x: x == "no fever")
        self.assertEqual(values, ["", "dyspnea"])
        self.assertFalse(warnings)
        model.rewrite_clinical.assert_called_once_with(["winded on stairs"])
        self.assertTrue(engine._lock.acquire(blocking=False))
        engine._lock.release()

    def test_timeout_discards_output_and_releases_lock(self):
        model = Mock()
        model.rewrite_clinical.side_effect = TimeoutError("budget")
        engine = self.engine(model)
        values, raw, warnings = clinical_rewrites(engine, ["winded on stairs"], lambda _: False)
        self.assertEqual(values, [""])
        self.assertEqual(raw, "")
        self.assertTrue(warnings)
        self.assertTrue(engine._lock.acquire(blocking=False))
        engine._lock.release()

    def test_busy_model_is_not_called(self):
        engine = self.engine()
        engine._lock = Mock()
        engine._lock.acquire.return_value = False
        self.assertTrue(clinical_rewrites(engine, ["winded on stairs"], lambda _: False)[2])
        engine._lock.acquire.assert_called_once_with(timeout=2)
        engine.models["reasoning"].rewrite_clinical.assert_not_called()
        engine._lock.release.assert_not_called()

    def test_unavailable_model_does_not_wait_for_loading(self):
        engine = self.engine()
        engine.ready = lambda: False
        self.assertTrue(clinical_rewrites(engine, ["winded on stairs"], lambda _: False)[2])
        engine.models["reasoning"].rewrite_clinical.assert_not_called()

    def test_large_note_bounded_without_dropping_original_positions(self):
        model = Mock()
        model.rewrite_clinical.return_value = (["dyspnea"] * 12, "reply")
        values, _, warnings = clinical_rewrites(self.engine(model), ["x" * 500] * 15, lambda _: False)
        self.assertEqual(values, ["dyspnea"] * 12 + [""] * 3)
        self.assertTrue(warnings)
        self.assertTrue(all(len(s) == 500 for s in model.rewrite_clinical.call_args.args[0]))

    def test_long_phrase_not_truncated_before_negation(self):
        engine = self.engine()
        values, _, warnings = clinical_rewrites(engine, ["x" * 501 + " no fever"], lambda _: False)
        self.assertEqual(values, [""])
        self.assertTrue(warnings)
        engine.models["reasoning"].rewrite_clinical.assert_not_called()

    def test_malformed_response_is_not_silently_zipped(self):
        model = Mock()
        model.rewrite_clinical.return_value = ([], "bad reply")
        values, _, warnings = clinical_rewrites(self.engine(model), ["winded on stairs"], lambda _: False)
        self.assertEqual(values, [""])
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
