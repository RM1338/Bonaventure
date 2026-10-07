"""Local model locations, shared by inference and the setup checker."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("BV_MODELS_DIR", ROOT / "models")).expanduser()
CLEAR_DIR = Path(os.environ.get("BV_CLEAR_DIR", MODELS_DIR / "CLEAR")).expanduser()
CLEAR_CODE = Path(os.environ.get("BV_CLEAR_CODE", CLEAR_DIR / "code")).expanduser()
CLEAR_CKPT = str(Path(os.environ.get("BV_CLEAR_CKPT", CLEAR_DIR / "best_model.pt")).expanduser())
CHEXZERO_DIR = Path(os.environ.get("BV_CHEXZERO_DIR", MODELS_DIR / "CheXzero")).expanduser()
CHEXZERO_CKPT = Path(os.environ.get(
    "BV_CHEXZERO_CKPT", CHEXZERO_DIR / "checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt"
)).expanduser()
MEDSAM_DIR = Path(os.environ.get("BV_MEDSAM_DIR", MODELS_DIR / "MedSAM")).expanduser()
MEDSAM_CKPT = Path(os.environ.get("BV_MEDSAM_CKPT", MEDSAM_DIR / "work_dir/MedSAM/medsam_vit_b.pth")).expanduser()
_LOCAL_MEDGEMMA = MODELS_DIR / "MedGemma"
MEDGEMMA_ID = os.environ.get("BV_MEDGEMMA") or (
    str(_LOCAL_MEDGEMMA) if (_LOCAL_MEDGEMMA / "config.json").exists() else "google/medgemma-1.5-4b-it"
)
