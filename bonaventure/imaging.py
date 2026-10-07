"""Scan loading, image-quality check, and the imaging-model engine (real models plug in here; mock until they load)."""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .knowledge import FINDINGS


class InvalidScan(Exception):
    pass


def load_scan(path):
    """Any supported file -> (8-bit grayscale PIL image, metadata dict)."""
    path = Path(path)
    meta = {"file": path.name, "view": "Medical image"}
    try:
        if path.suffix.lower() in (".dcm", ".dicom"):
            import pydicom
            ds = pydicom.dcmread(str(path))
            arr = ds.pixel_array.astype(np.float32)
            if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
                arr = arr.max() - arr
            lo, hi = np.percentile(arr, (0.5, 99.5))
            img = Image.fromarray((np.clip((arr - lo) / max(hi - lo, 1), 0, 1) * 255).astype(np.uint8))
            meta["patient_name"] = str(getattr(ds, "PatientName", "") or "").strip() or None
            meta["patient_id"] = str(getattr(ds, "PatientID", "") or "").strip() or None
            view = str(getattr(ds, "ViewPosition", "") or "").upper()
            meta["view"] = f"{view} medical image" if view in ("PA", "AP", "LL", "LATERAL") else "Medical image"
        else:
            img = ImageOps.exif_transpose(Image.open(path))
            meta["color"] = _colorfulness(img)
            img = img.convert("L")
    except Exception as e:  # unreadable / corrupt / unsupported
        raise InvalidScan(f"{path.name}: {e}") from e
    meta["width"], meta["height"] = img.size
    return img, meta


def _colorfulness(img):
    a = np.asarray(img.convert("RGB").resize((256, 256)), dtype=np.float32)
    return float(np.mean(np.abs(a[..., 0] - a[..., 1]) + np.abs(a[..., 1] - a[..., 2])))


def check_quality(img, meta):
    """Heuristic QC. Returns {state: acceptable|limited|poor, warnings: [...], metrics: {...}}."""
    a = np.asarray(img.resize((512, 512)), dtype=np.float32)
    lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    m = dict(min_side=min(img.size), mean=float(a.mean()), contrast=float(a.std()), sharpness=float(lap.var()), color=meta.get("color", 0.0))
    warnings, severe = [], False
    if m["color"] > 25:
        warnings.append("Image does not appear to be a radiograph (colour content detected)."); severe = True
    if m["min_side"] < 320:
        warnings.append("Very low resolution — fine detail cannot be assessed."); severe = True
    elif m["min_side"] < 768:
        warnings.append("Low resolution study.")
    if m["mean"] < 45:
        warnings.append("Underexposure detected.")
    elif m["mean"] > 205:
        warnings.append("Overexposure detected.")
    if m["contrast"] < 28:
        warnings.append("Low image contrast.")
    if m["sharpness"] < 12:
        warnings.append("Image appears blurred or heavily compressed.")
    state = "poor" if severe or len(warnings) >= 2 else "limited" if warnings else "acceptable"
    return dict(state=state, warnings=warnings, metrics={k: round(v, 2) for k, v in m.items()})


# ---------- model engine ----------

class ImagingEngine:
    """Loads imaging models once in the background and runs them per case.

    analyze() returns:
      sources:        [{role: primary|verifier, model, scores: {FINDING: 0..1}, thresholds}]
      localizations:  {FINDING: {bbox: [x0,y0,x1,y1] normalised, region_name, source}}
      descriptions:   {FINDING: [short radiological observations]}
      masks:          {FINDING: PNG data-url}   (optional segmentation refinement)
      timing:         {model: seconds}
    """

    def __init__(self):
        self.mock = os.environ.get("BV_MOCK") == "1"
        self.status = {"imaging": "loading", "reasoning": "loading"}
        self.models = {}
        self._loaded = threading.Event()  # status flips to "ready" per model; this fires only once self.models is complete
        self._lock = threading.Lock()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        if self.mock:
            self.status = {"imaging": "mock", "reasoning": "mock"}
            self._loaded.set()
            return
        try:
            from . import models  # heavy: torch + checkpoints
            self.models = models.load_all(self.status)
        except Exception as e:
            print(f"[imaging] real models unavailable: {e!r}", flush=True)
            self.load_error = repr(e)
            for key in self.status:
                if self.status[key] == "loading":
                    self.status[key] = "unavailable"
            self.status["imaging"] = "unavailable"
        finally:
            self._loaded.set()

    def ready(self):
        return self._loaded.is_set()

    def analyze(self, img, scan_path):
        self._loaded.wait()
        with self._lock:  # one GPU, one case at a time
            if self.mock:
                return _mock_analyze(img, scan_path)
            if getattr(self, "load_error", None):
                raise RuntimeError(f"Real model loading failed: {self.load_error}")
            from . import models
            result = models.analyze(self.models, img)
            if not result["sources"]:
                raise RuntimeError("no imaging model produced output")  # surfaced as IMAGE_MODEL_FAILED, never silently empty
            return result


def _mock_analyze(img, scan_path):
    """Deterministic fake output for UI development. A '<scan>.mock.json' sidecar overrides it for demo design."""
    sidecar = Path(str(scan_path) + ".mock.json")
    if sidecar.exists():
        return json.loads(sidecar.read_text())
    seed = int(hashlib.sha1(np.asarray(img.resize((64, 64))).tobytes()).hexdigest(), 16)
    rng = np.random.default_rng(seed % 2**32)
    names = list(FINDINGS)
    primary = {f: float(rng.uniform(0.2, 0.45)) for f in names}
    verifier = {f: float(rng.uniform(0.2, 0.45)) for f in names}
    hot = rng.choice(names, 2, replace=False)
    primary[hot[0]], verifier[hot[0]] = 0.82, 0.74      # concordant positive
    primary[hot[1]], verifier[hot[1]] = 0.68, 0.31      # discordant -> conflict
    boxes = {"PLEURAL_EFFUSION": [0.58, 0.66, 0.86, 0.9], "CARDIOMEGALY": [0.34, 0.42, 0.72, 0.8], "PNEUMOTHORAX": [0.6, 0.12, 0.88, 0.42],
             "CONSOLIDATION": [0.16, 0.5, 0.42, 0.78], "PULMONARY_EDEMA": [0.28, 0.32, 0.72, 0.68], "ATELECTASIS": [0.18, 0.64, 0.44, 0.84]}
    return dict(
        sources=[dict(role="primary", model="mock-primary", scores=primary, thresholds=[0.45, 0.55, 0.65]),
                 dict(role="verifier", model="mock-verifier", scores=verifier, thresholds=[0.45, 0.55, 0.65])],
        localizations={f: dict(bbox=boxes[f], region_name=FINDINGS[f]["region"], source="mock") for f in hot if f in boxes},
        descriptions={f: [f"Mock observation consistent with {FINDINGS[f]['name'].lower()}"] for f in hot},
        masks={}, timing={"mock": 0.4})
