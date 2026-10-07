"""Exercise Windows integration on any OS without starting a native GUI."""
import ast
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch

from bonaventure import context

ROOT = Path(__file__).parents[1]


class WindowsIntegrationTests(unittest.TestCase):
    def test_pdf_history_falls_back_when_poppler_is_missing(self):
        reader = Mock(return_value=S(pages=[S(extract_text=lambda: "Patient history"),
                                           S(extract_text=lambda: None)]))
        with patch.object(context.subprocess, "run", side_effect=FileNotFoundError), \
                patch.dict(sys.modules, {"pypdf": S(PdfReader=reader)}):
            self.assertEqual(context.read_pages(Path("history.pdf")), ["Patient history", ""])
            self.assertEqual(context.pdf_page_count(Path("history.pdf")), 2)

    def test_pdf_fallback_failure_remains_a_parse_error(self):
        with patch.object(context.subprocess, "run", side_effect=FileNotFoundError), \
                patch.dict(sys.modules, {"pypdf": S(PdfReader=Mock(side_effect=ValueError("broken")))}):
            with self.assertRaisesRegex(context.HistoryParseError, "broken"):
                context.read_pages(Path("history.pdf"))

    def test_reused_review_navigates_to_the_new_case(self):
        tree = ast.parse((ROOT / "bonaventure/desktop.py").read_text())
        api_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
        namespace = {}
        exec(compile(ast.Module(body=[api_node], type_ignores=[]), "desktop.Api", "exec"), namespace)
        api = namespace["Api"].__new__(namespace["Api"])
        api._scan, api._histories = {}, [{}]
        api._review = Mock(real_url="http://localhost/review.html?case=BV-001")
        namespace["REVIEW_TITLE"] = "Bonaventure — {}"
        api.open_review("BV-002")
        api._review.load_url.assert_called_once_with("http://localhost/review.html?case=BV-002")
        self.assertEqual(api._current, "BV-002")
        self.assertEqual(api._histories, [])

    def test_windows_shell_never_imports_linux_or_mac(self):
        fake_base = type("Api", (), {})
        spec = importlib.util.spec_from_file_location("bonaventure._windows_test", ROOT / "bonaventure/windows_app.py")
        module = importlib.util.module_from_spec(spec)
        desktop = S(Api=fake_base, ISLAND_TITLE="Bonaventure", UI=ROOT / "bonaventure/ui", _review_window=Mock())
        with patch.dict(sys.modules, {"webview": S(), "bonaventure.desktop": desktop}):
            spec.loader.exec_module(module)
        api = module.WindowsApi.__new__(module.WindowsApi)
        api._launcher = Mock()
        api._launcher_visible = True
        api.on_shortcut()
        api._launcher.hide.assert_called_once()
        self.assertFalse(api._launcher_visible)
        api.on_shortcut()
        api._launcher.show.assert_called_once()
        self.assertTrue(api._launcher_visible)
        api._launcher_screen = S(x=100, y=50, width=1920, height=1080)
        api._place_island(660, 300, "intake")
        api._launcher.move.assert_called_once_with(730, 440)

    def test_missing_models_are_audited_and_medSAM_is_skipped(self):
        tree = ast.parse((ROOT / "bonaventure/models.py").read_text())
        analyze = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "analyze")
        namespace = {"time": __import__("time"), "CONCEPT_READER": {}}
        exec(compile(ast.Module(body=[analyze], type_ignores=[]), "models.analyze", "exec"), namespace)
        result = namespace["analyze"]({}, Mock())
        audit = {item["model"]: item["state"] for item in result["model_audit"]}
        self.assertEqual(audit["primary"], "unavailable")
        self.assertEqual(audit["MedGemma"], "unavailable")
        self.assertEqual(audit["MedSAM"], "unavailable")
        result = namespace["analyze"]({"segmentation": Mock()}, Mock())
        self.assertEqual(result["model_audit"][-1]["state"], "skipped")


if __name__ == "__main__":
    unittest.main()
