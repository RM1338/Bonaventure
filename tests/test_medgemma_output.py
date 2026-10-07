import ast
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock


class MedGemmaOutputTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / "bonaventure/models.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MedGemma")
        ask = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_ask")
        self.ns = dict(generate_with_budget=Mock(return_value=[[1, 2]]), image_generation_seconds=lambda _: "600")
        exec(compile(ast.Module(body=[ask], type_ignores=[]), "MedGemma._ask", "exec"), self.ns)
        self.processor = Mock()
        self.processor.apply_chat_template.return_value.to.return_value = {"input_ids": S(shape=[1, 1])}
        self.model = S(device=S(type="mps"), dtype="bf16")
        self.instance = S(processor=self.processor, model=self.model)

    def test_empty_special_token_output_is_failure(self):
        self.processor.decode.side_effect = ["", "<eos>"]
        with self.assertRaisesRegex(RuntimeError, "no image response"):
            self.ns["_ask"](self.instance, Mock(), "survey", 300)

    def test_nonempty_raw_text_preserved(self):
        self.processor.decode.return_value = '{"findings": []}'
        self.assertEqual(self.ns["_ask"](self.instance, Mock(), "survey", 300), '{"findings": []}')
        self.processor.apply_chat_template.return_value.to.assert_called_once_with(self.model.device, dtype="bf16")
