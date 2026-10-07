"""Check local setup without loading multi-gigabyte models: python scripts/check_setup.py."""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bonaventure import model_paths as paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true", help="check only dependencies needed for mock mode")
    args = parser.parse_args()
    missing = []

    def check(label, ok):
        print(f"{'OK     ' if ok else 'MISSING'} {label}")
        if not ok:
            missing.append(label)

    def file(label, path):
        path = Path(path)
        ok = path.is_file() and path.stat().st_size > 0
        if ok:
            with path.open('rb') as stream:
                ok = not stream.read(100).startswith(b'version https://git-lfs.github.com/spec/')
        check(f"{label}: {path}", ok)

    deps = {"numpy": "numpy", "Pillow": "PIL", "pywebview": "webview", "WeasyPrint": "weasyprint"}
    if not args.mock:
        deps.update({name: name for name in (
            "torch", "torchvision", "transformers", "accelerate", "huggingface_hub",
            "pandas", "ftfy", "regex", "scipy", "sklearn", "h5py", "tqdm", "pydicom",
        )})
    print(f"Python: {sys.executable}")
    for label, module in deps.items():
        check(f"Python package {label}", importlib.util.find_spec(module) is not None)
    check("pdftotext (install poppler for history PDFs)", shutil.which("pdftotext") is not None)

    if not args.mock:
        file("CLEAR source", paths.CLEAR_CODE / "src/clear/hub.py")
        file("CLEAR weights", paths.CLEAR_CKPT)
        file("CLEAR concept embeddings", paths.CLEAR_DIR / "concept_embeddings_368294.pt")
        file("CLEAR concept vocabulary", paths.CLEAR_DIR / "mimic_concepts.csv")
        file("CheXzero source", paths.CHEXZERO_DIR / "model.py")
        file("CheXzero tokenizer", paths.CHEXZERO_DIR / "bpe_simple_vocab_16e6.txt.gz")
        file("CheXzero weights", paths.CHEXZERO_CKPT)
        file("MedSAM source", paths.MEDSAM_DIR / "segment_anything/build_sam.py")
        file("MedSAM weights", paths.MEDSAM_CKPT)
        gemma = Path(paths.MEDGEMMA_ID)
        if gemma.is_dir():
            for filename in ("config.json", "preprocessor_config.json", "tokenizer.json", "model.safetensors.index.json"):
                file("MedGemma", gemma / filename)
            index = gemma / "model.safetensors.index.json"
            if index.is_file():
                try:
                    shards = set(json.loads(index.read_text())["weight_map"].values())
                    for shard in sorted(shards):
                        file("MedGemma weight shard", gemma / shard)
                except (ValueError, KeyError) as error:
                    check(f"MedGemma weight index is valid ({error})", False)
        else:
            check(f"Local MedGemma directory (currently {paths.MEDGEMMA_ID}; remote loading requires Hugging Face access)", False)

    print(f"\n{len(missing)} missing requirement(s)." if missing else "\nSetup checks passed. Native GUI and model inference still need a runtime check.")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
