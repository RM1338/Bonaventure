"""Run real export/opener methods with only platform and PDF creation mocked."""
import ast
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch


class ReportOpenTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / "bonaventure/desktop.py").read_text())
        opener = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_open")
        api = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
        self.namespace = dict(Path=Path, sys=S(platform="darwin"), os=Mock(), shutil=Mock(), subprocess=Mock(),
                              pipeline=S(ROOT=Path("/project")), report=Mock())
        exec(compile(ast.Module(body=[opener, api], type_ignores=[]), "desktop", "exec"), self.namespace)
        self.api = self.namespace["Api"].__new__(self.namespace["Api"])
        self.api.get_case = Mock(return_value={"case_id": "BV-004"})
        self.namespace["report"].generate.return_value = Path("/project/cases/BV-004/report.pdf")

    def test_export_opens_macos_pdf(self):
        result = self.api.export_report("BV-004")
        self.assertTrue(result["opened"])
        self.assertEqual(result["path"], "cases/BV-004/report.pdf")
        self.assertEqual(self.namespace["subprocess"].run.call_args.args[0], ["/usr/bin/open", "/project/cases/BV-004/report.pdf"])

    def test_linux_retains_xdg_open(self):
        self.namespace["sys"].platform = "linux"
        self.namespace["shutil"].which.return_value = "/usr/bin/xdg-open"
        self.assertTrue(self.api.export_report("BV-004")["opened"])
        self.assertEqual(self.namespace["subprocess"].run.call_args.args[0][0], "/usr/bin/xdg-open")

    def test_failed_open_preserves_successful_export(self):
        self.namespace["subprocess"].run.side_effect = subprocess.CalledProcessError(1, "open")
        result = self.api.export_report("BV-004")
        self.assertFalse(result["opened"])
        self.assertIn("warning", result)
        self.assertIn("path", result)
        self.assertNotIn("error", result)

    def test_pdf_failure_does_not_open(self):
        self.namespace["report"].generate.side_effect = RuntimeError("PDF failed")
        self.assertIn("error", self.api.export_report("BV-004"))
        self.namespace["subprocess"].run.assert_not_called()
