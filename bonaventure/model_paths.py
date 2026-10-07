"""Where the models live. Both supported layouts are searched, so neither machine needs configuration:
    in-repo  models/CLEAR, models/CheXzero, models/MedSAM, models/MedGemma          (macOS setup, scripts/install_macos.py)
    home     ~/bonaventure/models/{clear,medgemma-1.5-4b-it} + repo CLEAR/, CheXzero/, MedSAM/   (Linux setup, SETUP_TEAMMATE.txt)
Any path can be forced with its BV_* environment variable."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("BV_MODELS_DIR", ROOT / "models")).expanduser()
HOME_MODELS = Path.home() / "bonaventure/models"


def _first(env, *candidates, must_have=None):
    """The env override, else the first candidate that exists (and contains `must_have`), else the first candidate."""
    if os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    for c in candidates:
        c = Path(c).expanduser()
        if c.exists() and (must_have is None or (c / must_have).exists()):
            return c
    return Path(candidates[0]).expanduser()


CLEAR_DIR = _first("BV_CLEAR_DIR", MODELS_DIR / "CLEAR", HOME_MODELS / "clear", must_have="best_model.pt")
CLEAR_CODE = _first("BV_CLEAR_CODE", CLEAR_DIR / "code", ROOT / "CLEAR", must_have="src")
CLEAR_CKPT = str(_first("BV_CLEAR_CKPT", CLEAR_DIR / "best_model.pt"))
CHEXZERO_DIR = _first("BV_CHEXZERO_DIR", MODELS_DIR / "CheXzero", ROOT / "CheXzero", must_have="model.py")
CHEXZERO_CKPT = _first("BV_CHEXZERO_CKPT", CHEXZERO_DIR / "checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt")
MEDSAM_DIR = _first("BV_MEDSAM_DIR", MODELS_DIR / "MedSAM", ROOT / "MedSAM", must_have="segment_anything")
MEDSAM_CKPT = _first("BV_MEDSAM_CKPT", MEDSAM_DIR / "work_dir/MedSAM/medsam_vit_b.pth")
_medgemma = _first("BV_MEDGEMMA", MODELS_DIR / "MedGemma", MODELS_DIR / "medgemma-1.5-4b-it", HOME_MODELS / "medgemma-1.5-4b-it", must_have="config.json")
MEDGEMMA_ID = str(_medgemma) if (_medgemma / "config.json").exists() else "google/medgemma-1.5-4b-it"
WHISPER_LIVE_DIR = _first("BV_WHISPER_LIVE", MODELS_DIR / "whisper-base.en", HOME_MODELS / "whisper-base.en", must_have="config.json")
WHISPER_FINAL_DIR = _first("BV_WHISPER", MODELS_DIR / "whisper-small.en", HOME_MODELS / "whisper-small.en", must_have="config.json")


if __name__ == "__main__":
    for k, v in dict(CLEAR_DIR=CLEAR_DIR, CLEAR_CODE=CLEAR_CODE, CLEAR_CKPT=CLEAR_CKPT, CHEXZERO_DIR=CHEXZERO_DIR, CHEXZERO_CKPT=CHEXZERO_CKPT,
                     MEDSAM_DIR=MEDSAM_DIR, MEDSAM_CKPT=MEDSAM_CKPT, MEDGEMMA_ID=MEDGEMMA_ID).items():
        print(f"{k:<14} {v}  {'ok' if Path(str(v)).exists() else 'MISSING'}")
