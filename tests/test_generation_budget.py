import unittest
from unittest.mock import Mock, patch

from bonaventure.generation import generate_with_budget


class GenerationBudgetTests(unittest.TestCase):
    def test_output_after_budget_is_discarded(self):
        model = Mock()
        model.generate.return_value = "partial clinical claim"
        with patch("bonaventure.generation.time.monotonic", side_effect=[10, 41]):
            with self.assertRaisesRegex(TimeoutError, "partial output discarded"):
                generate_with_budget(model, {"input_ids": "input"}, 48, 30, "rewrite")
        model.generate.assert_called_once_with(input_ids="input", max_new_tokens=48, do_sample=False, max_time=30)

    def test_successful_generation_preserved(self):
        model = Mock()
        model.generate.return_value = "complete"
        with patch("bonaventure.generation.time.monotonic", side_effect=[10, 11]):
            self.assertEqual(generate_with_budget(model, {}, 48, "30", "rewrite"), "complete")

    def test_invalid_budget_rejected_before_call(self):
        model = Mock()
        for budget in (0, -1, "nan", "inf", "invalid"):
            with self.assertRaises(ValueError):
                generate_with_budget(model, {}, 48, budget, "rewrite")
        model.generate.assert_not_called()
