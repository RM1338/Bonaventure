"""Hover behavior can be checked without a Mac or model dependencies."""
import unittest

from bonaventure.launcher_hover import HoverIntent


class HoverIntentTests(unittest.TestCase):
    def test_brief_pass_below_notch_does_not_open(self):
        intent = HoverIntent()
        self.assertIsNone(intent.update(0, hotspot=True, inside=False, visible=False))
        self.assertIsNone(intent.update(0.1, hotspot=False, inside=False, visible=False))
        self.assertIsNone(intent.update(1, hotspot=False, inside=False, visible=False))

    def test_hover_opens_only_after_continuous_dwell(self):
        intent = HoverIntent()
        intent.update(0, hotspot=True, inside=False, visible=False)
        intent.update(0.1, hotspot=False, inside=False, visible=False)
        self.assertIsNone(intent.update(1, hotspot=True, inside=False, visible=False))
        self.assertIsNone(intent.update(1.1, hotspot=True, inside=False, visible=False))
        self.assertEqual(intent.update(1.3, hotspot=True, inside=False, visible=False), "open")

    def test_moving_from_notch_into_launcher_keeps_it_open(self):
        intent = HoverIntent()
        for now in (0, 1, 10):
            self.assertIsNone(intent.update(now, hotspot=False, inside=True, visible=True))

    def test_leave_grace_allows_cursor_to_return(self):
        intent = HoverIntent()
        intent.update(0, hotspot=False, inside=False, visible=True)
        self.assertIsNone(intent.update(0.3, hotspot=False, inside=True, visible=True))
        self.assertIsNone(intent.update(1, hotspot=False, inside=False, visible=True))
        self.assertIsNone(intent.update(1.3, hotspot=False, inside=False, visible=True))
        self.assertEqual(intent.update(1.6, hotspot=False, inside=False, visible=True), "close")

    def test_manual_interaction_prevents_auto_dismissal(self):
        intent = HoverIntent()
        for now in (0, 1, 100):
            self.assertIsNone(intent.update(now, hotspot=False, inside=False, visible=True, pinned=True))

    def test_analysis_does_not_auto_dismiss(self):
        intent = HoverIntent()
        for now in (0, 1, 100):
            self.assertIsNone(intent.update(now, hotspot=False, inside=False, visible=True, processing=True))

    def test_hidden_window_does_not_inherit_close_timer(self):
        intent = HoverIntent()
        intent.update(0, hotspot=False, inside=False, visible=True)
        self.assertIsNone(intent.update(1, hotspot=True, inside=False, visible=False))
        self.assertEqual(intent.update(1.3, hotspot=True, inside=False, visible=False), "open")
        self.assertIsNone(intent.update(2, hotspot=False, inside=False, visible=True))
        self.assertEqual(intent.update(2.6, hotspot=False, inside=False, visible=True), "close")


if __name__ == "__main__":
    unittest.main()
