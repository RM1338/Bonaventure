import os
import unittest
from types import SimpleNamespace as S
from unittest.mock import Mock, patch

from bonaventure.model_runtime import medgemma_device, image_generation_seconds, load_medgemma


class ModelRuntimeTests(unittest.TestCase):
    def torch(self, cuda=False, mps=False):
        return S(cuda=S(is_available=lambda: cuda), backends=S(mps=S(is_available=lambda: mps)),
                 float16="fp16", bfloat16="bf16")

    def test_mac_auto_uses_mps(self):
        with patch.dict(os.environ, {"BV_MEDGEMMA_DEVICE": "auto"}), patch("bonaventure.model_runtime.sys.platform", "darwin"):
            self.assertEqual(medgemma_device(self.torch(mps=True)), "mps")

    def test_linux_and_cuda_behavior_preserved(self):
        with patch.dict(os.environ, {"BV_MEDGEMMA_DEVICE": "auto"}), patch("bonaventure.model_runtime.sys.platform", "linux"):
            self.assertEqual(medgemma_device(self.torch(mps=True)), "cpu")
            self.assertEqual(medgemma_device(self.torch(cuda=True)), "cuda")

    def test_explicit_unavailable_backend_rejected(self):
        with patch.dict(os.environ, {"BV_MEDGEMMA_DEVICE": "mps"}), patch("bonaventure.model_runtime.sys.platform", "darwin"):
            with self.assertRaises(RuntimeError):
                medgemma_device(self.torch())

    def test_cpu_override_supported_on_mac(self):
        with patch.dict(os.environ, {"BV_MEDGEMMA_DEVICE": "cpu"}), patch("bonaventure.model_runtime.sys.platform", "darwin"):
            self.assertEqual(medgemma_device(self.torch(mps=True)), "cpu")

    def test_mps_load_uses_fp16_eager_and_no_cuda_quantization(self):
        loader, quantization = Mock(), Mock()
        with patch.dict(os.environ, {"BV_MEDGEMMA_DEVICE": "auto"}), patch("bonaventure.model_runtime.sys.platform", "darwin"):
            load_medgemma(self.torch(mps=True), loader, quantization, "local-model")
        options = loader.from_pretrained.call_args.kwargs
        self.assertEqual(options["device_map"], {"": "mps"})
        self.assertEqual(options["dtype"], "fp16")
        self.assertEqual(options["attn_implementation"], "eager")
        quantization.assert_not_called()

    def test_cuda_quantization_preserved(self):
        loader, quantization = Mock(), Mock()
        with patch.dict(os.environ, {"BV_MEDGEMMA_DEVICE": "auto"}):
            load_medgemma(self.torch(cuda=True), loader, quantization, "local-model")
        self.assertEqual(loader.from_pretrained.call_args.kwargs["device_map"], {"": 0})
        quantization.assert_called_once_with(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype="bf16")

    def test_device_budgets_and_user_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(image_generation_seconds("cpu"), "1800")
            self.assertEqual(image_generation_seconds("mps"), "600")
            self.assertEqual(image_generation_seconds("cuda"), "180")
        with patch.dict(os.environ, {"BV_IMAGE_GENERATION_SECONDS": "42"}):
            self.assertEqual(image_generation_seconds("cpu"), "42")
