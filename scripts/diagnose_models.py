#!/usr/bin/env python3
"""Run real load/inference checks in separate processes to release RAM between models.

This is a runtime smoke test, not a clinical accuracy benchmark. Close the app first.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CHECKS = ("CLEAR", "CheXzero", "CLEAR-concepts", "MedSAM", "MedGemma-text",
          "MedGemma-image", "Whisper-live", "Whisper-final", "MiniLM")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_tied(model):
    if getattr(model.config, "tie_word_embeddings", False):
        inputs, outputs = model.get_input_embeddings(), model.get_output_embeddings()
        require(inputs is not None and outputs is not None, "missing input/output embeddings")
        require(inputs.weight.data_ptr() == outputs.weight.data_ptr(),
                "checkpoint expects tied embeddings but input/output weights are not shared")
        print("  input/output embeddings share weights", flush=True)


def check_one(name, scan):
    import numpy as np
    import torch
    from PIL import Image
    from bonaventure import models
    from bonaventure.knowledge import FINDINGS
    image = Image.open(scan).convert("L")
    print(f"  torch={torch.__version__}; imaging device={models.DEVICE}", flush=True)
    with torch.inference_mode():
        if name in ("CLEAR", "CheXzero", "CLEAR-concepts"):
            reader = (models.load_chexzero if name == "CheXzero" else models.load_clear)()
            scores = reader.scores(image)
            require(set(scores) == set(FINDINGS), "missing finding scores")
            require(all(math.isfinite(v) and 0 <= v <= 1 for v in scores.values()), "invalid scores")
            if name == "CLEAR-concepts":
                bank = models.ConceptBank(reader.model)
                _, top = bank.explain(reader.last_features)
                require(bool(top), "empty concept retrieval")
        elif name == "MedSAM":
            sam = models.MedSAM()
            checked = []
            def decoder_checked(module, inputs, outputs):
                checked.append(bool(torch.isfinite(outputs[0]).all()))
            hook = sam.model.mask_decoder.register_forward_hook(decoder_checked)
            try:
                outlines = sam.outline(image, {"TEST": [0.2, 0.2, 0.8, 0.8]})
            finally:
                hook.remove()
            require(checked and all(checked), "segmentation decoder produced invalid/no output")
            require(all(math.isfinite(c) and 0 <= c <= 1 for pts in outlines.values() for pt in pts for c in pt),
                    "invalid segmentation coordinates")
            print(f"  decoder ran; accepted outlines={len(outlines)} (empty mask can be valid)", flush=True)
        elif name.startswith("MedGemma"):
            gemma = models.MedGemma()
            check_tied(gemma.model)
            print(f"  actual device={gemma.model.device}; dtype={gemma.model.dtype}", flush=True)
            if name.endswith("text"):
                rewrites, _ = gemma.rewrite_clinical(["gets winded on the stairs"])
                require(len(rewrites) == 1 and bool(rewrites[0].strip()), "no numbered clinical rewrite")
            else:
                text = gemma._ask(image, "Describe the image in one short sentence.", 32)
                require(bool(text.strip()), "empty image response")
        elif name.startswith("Whisper"):
            from bonaventure.dictation import _Whisper, LIVE_DIR, FINAL_DIR, RATE
            whisper = _Whisper(LIVE_DIR if name.endswith("live") else FINAL_DIR)
            check_tied(whisper.model)
            # Exercise the actual encoder/decoder, bypassing the app's silence shortcut.
            features = whisper.processor(np.zeros(RATE, dtype=np.float32), sampling_rate=RATE,
                                         return_tensors="pt").input_features
            decoder = torch.tensor([[whisper.model.config.decoder_start_token_id]])
            logits = whisper.model(input_features=features, decoder_input_ids=decoder).logits
            require(bool(torch.isfinite(logits).all()), "non-finite speech logits")
            ids = whisper.model.generate(features, max_new_tokens=8)
            require(ids.numel() > 0, "empty speech generation")
            whisper.processor.batch_decode(ids, skip_special_tokens=True)
            print("  synthetic audio decoded; microphone/recognition accuracy not tested", flush=True)
        elif name == "MiniLM":
            from bonaventure.semantic import MODEL_DIR, matcher
            if not MODEL_DIR.exists():
                print("  optional MiniLM not installed", flush=True)
                return 2
            require(matcher().match("shortness of breath") is not None, "known symptom not matched")
    return 0


def run_check(name, scan, timeout):
    started = time.monotonic()
    print(f"\n{name}: loading and testing", flush=True)
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--only", name,
                                 "--scan", str(scan)], env=env, timeout=timeout)
        state = "passed" if result.returncode == 0 else "skipped" if result.returncode == 2 else "failed"
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s; process stopped", flush=True)
        state = "timeout"
    return dict(model=name, status=state, seconds=round(time.monotonic() - started, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, default=ROOT / "sample_data/scans/kerley_b.jpg")
    parser.add_argument("--timeout", type=float, default=600, help="hard time limit per model, including load (seconds)")
    parser.add_argument("--report", type=Path, default=ROOT / "cases/model-health.json")
    parser.add_argument("--only", choices=CHECKS, help="test one model (also used by subprocess workers)")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    if args.only:
        try:
            return check_one(args.only, args.scan)
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}", flush=True)
            return 1
    print(f"Python: {sys.executable}; close Bonaventure before this RAM-intensive check", flush=True)
    results = []
    args.report.parent.mkdir(parents=True, exist_ok=True)
    for name in CHECKS:
        results.append(run_check(name, args.scan, args.timeout))
        args.report.write_text(json.dumps(results, indent=2))
        print(f"  {results[-1]['status'].upper()}: {results[-1]['seconds']}s", flush=True)
    print(f"\nReport: {args.report}")
    return int(any(r["status"] in ("failed", "timeout") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
