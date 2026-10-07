"""Evaluate CLEAR's concept bank as a detector: for every finding, score = -log10(rank of the best matching, non-negated
report phrase among 368,294). Same films as scripts/calibrate.py. Writes bonaventure/concept_calibration.json with per-finding
AUROC and the rank cut-offs at 90% sensitivity / Youden / 90% specificity.

    PYTHONPATH=. .venv/bin/python scripts/eval_concepts.py
"""
import io
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import roc_auc_score, roc_curve

from bonaventure import models
from bonaventure.knowledge import FINDINGS
from scripts.calibrate import CHEXPERT, DATA, NIH, NIH_NEGATIVES, NIH_POS_PER_FINDING

OUT = Path(__file__).resolve().parent.parent / "bonaventure" / "concept_calibration.json"
TOP_K = 5000


def ranks_for(clear, bank, img):
    clear.scores(img)  # sets clear.last_features
    out, _ = bank.explain(clear.last_features, top_k=TOP_K, per_finding=1)
    return {f: (out[f]["for"][0][1] if out[f]["for"] else TOP_K * 10) for f in FINDINGS}


def evaluate(result, source, ranks, labels):
    for f, y in labels.items():
        if y.sum() < 5:
            continue
        s = -np.log10(np.array([r[f] for r in ranks], dtype=float))
        fpr, tpr, thr = roc_curve(y, s)
        cut = lambda t: int(round(10 ** (-t))) if np.isfinite(t) else 1
        result[f] = dict(source=source, auroc=round(float(roc_auc_score(y, s)), 3), n_pos=int(y.sum()), n_neg=int((1 - y).sum()),
                         rank_at_90_sens=cut(thr[np.argmax(tpr >= 0.90)]), rank_at_youden=cut(thr[np.argmax(tpr - fpr)]),
                         rank_at_90_spec=cut(thr[np.nonzero(fpr <= 0.10)[0][-1]]))


def main():
    torch.set_num_threads(8)
    clear = models.load_clear()
    bank = models.ConceptBank(clear.model)
    result, t0 = {}, time.time()

    d = pd.read_parquet(DATA / "chexpert_valid.parquet")
    d = d[d["Frontal/Lateral"] == 0].reset_index(drop=True)
    ranks = []
    for i, b in enumerate(d["image"]):
        ranks.append(ranks_for(clear, bank, Image.open(io.BytesIO(b["bytes"])).convert("L")))
        if i % 50 == 0:
            print(f"CheXpert {i}/{len(d)} {time.time() - t0:.0f}s", flush=True)
    evaluate(result, "CheXpert", ranks, {f: (d[c].to_numpy() == 3).astype(int) for f, c in CHEXPERT.items()})

    nih = pd.concat([pd.read_parquet(p, columns=["image", "label_names", "view_position"]) for p in sorted(DATA.glob("nih_test_*.parquet"))])
    nih = nih[nih["view_position"].isin(["PA", "AP"])].reset_index(drop=True)
    rnd, pick = random.Random(7), set()
    for f, lab in NIH.items():
        pos = [i for i, names in enumerate(nih["label_names"]) if lab in list(names)]
        pick.update(rnd.sample(pos, min(NIH_POS_PER_FINDING, len(pos))))
    normals = [i for i, names in enumerate(nih["label_names"]) if len(names) == 0 or list(names) == ["No Finding"]]
    pick.update(rnd.sample(normals, min(NIH_NEGATIVES, len(normals))))
    sub = nih.iloc[sorted(pick)].reset_index(drop=True)
    ranks = []
    for i, b in enumerate(sub["image"]):
        ranks.append(ranks_for(clear, bank, Image.open(io.BytesIO(b["bytes"])).convert("L")))
        if i % 50 == 0:
            print(f"NIH {i}/{len(sub)} {time.time() - t0:.0f}s", flush=True)
    evaluate(result, "NIH", ranks, {f: np.array([lab in list(n) for n in sub["label_names"]], dtype=int) for f, lab in NIH.items()})

    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT}\n{'finding':<22}{'src':<10}{'pos':>4} {'AUROC':>6}  rank@90sens  rank@youden  rank@90spec")
    for f, r in result.items():
        print(f"{f:<22}{r['source']:<10}{r['n_pos']:>4} {r['auroc']:>6}  {r['rank_at_90_sens']:>11}  {r['rank_at_youden']:>11}  {r['rank_at_90_spec']:>11}")


if __name__ == "__main__":
    main()
