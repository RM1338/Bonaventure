"""Select a MedGemma backend without changing the image readers or segmentation."""
import os
import sys


def medgemma_device(torch):
    requested = os.environ.get("BV_MEDGEMMA_DEVICE", "auto").lower()
    cuda = torch.cuda.is_available()
    mps = sys.platform == "darwin" and getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available()
    if requested == "auto":
        return "cuda" if cuda else "mps" if mps else "cpu"
    if requested not in ("cuda", "mps", "cpu"):
        raise ValueError("BV_MEDGEMMA_DEVICE must be auto, cuda, mps or cpu")
    if requested == "cuda" and not cuda or requested == "mps" and not mps:
        raise RuntimeError(f"Requested MedGemma device {requested} is unavailable")
    return requested


def image_generation_seconds(device):
    return os.environ.get("BV_IMAGE_GENERATION_SECONDS", "1800" if device == "cpu" else "600" if device == "mps" else "180")


def load_medgemma(torch, loader, quantization, path):
    device = medgemma_device(torch)
    dtype = torch.bfloat16
    if device == "mps":
        try:
            torch.empty(1, dtype=torch.bfloat16, device="mps")
        except (RuntimeError, TypeError):
            # Gemma can overflow in float16. Older macOS needs float32 instead.
            dtype = torch.float32
    options = dict(device_map={"": 0} if device == "cuda" else {"": "mps"} if device == "mps" else None,
                   dtype=dtype,
                   quantization_config=quantization(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                    bnb_4bit_compute_dtype=torch.bfloat16) if device == "cuda" else None)
    if device == "mps":
        # Avoid backend-specific fused attention paths.
        options["attn_implementation"] = "eager"
    model = loader.from_pretrained(path, **options).eval()
    print(f"[models] MedGemma device={model.device}, dtype={model.dtype}, "
          f"image generation budget={image_generation_seconds(device)}s", flush=True)
    return model
