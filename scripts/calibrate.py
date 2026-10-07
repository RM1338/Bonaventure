"""Calibrate the image readers on labelled chest X-rays and write bonaventure/calibration.json.

Each finding is evaluated on the best-labelled source that has enough positives:
    CheXpert v1.0 validation  radiologist consensus, 202 frontal films     (danjacobellis/chexpert)
    NIH ChestX-ray14 test     NLP-mined labels, sampled per finding         (timm/nih-chest-xray-14, 2 shards)
For every finding and reader the evidence levels come from that finding's ROC curve:
    weak      lowest score that still catches 90% of positives   (sensitivity >= 0.90)
    moderate  Youden's J optimum
    strong    score above which 90% of negatives are excluded     (specificity >= 0.90)

    PYTHONPATH=. .venv/bin/python scripts/calibrate.py
"""
import io
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import roc_auc_score, roc_curve

from bonaventure import models
from bonaventure.knowledge import FINDINGS

DATA = Path.home() / "bonaventure/data"
OUT = Path(__file__).resolve().parent.parent / "bonaventure" / "calibration.json"
CHEXPERT = {"PLEURAL_EFFUSION": "Pleural Effusion", "CARDIOMEGALY": "Cardiomegaly", "PNEUMOTHORAX": "Pneumothorax", "CONSOLIDATION": "Consolidation",
            "PULMONARY_EDEMA": "Edema", "ATELECTASIS": "Atelectasis", "ENLARGED_MEDIASTINUM": "Enlarged Cardiomediastinum", "SUPPORT_DEVICES": "Support Devices"}
NIH = {"PNEUMONIA": "Pneumonia", "LUNG_NODULE": "Nodule", "LUNG_MASS": "Mass", "EMPHYSEMA": "Emphysema", "FIBROSIS": "Fibrosis",
       "PLEURAL_THICKENING": "Pleural_Thickening", "HERNIA": "Hernia"}
NIH_POS_PER_FINDING, NIH_NEGATIVES = 60, 300


def thresholds(y, s):
    fpr, tpr, thr = roc_curve(y, s)
    thr = np.clip(thr, 0, 1)
    weak, moderate, strong = thr[np.argmax(tpr >= 0.90)], thr[np.argmax(tpr - fpr)], thr[np.nonzero(fpr <= 0.10)[0][-1]]
    w, m, st = sorted([float(weak), float(moderate), float(strong)])
    pred = s >= m
    return dict(thresholds=[round(w, 4), round(m, 4), round(st, 4)],
                sens_at_moderate=round(float(pred[y == 1].mean()), 3), spec_at_moderate=round(float((~pred[y == 0]).mean()), 3))


def score_all(readers, images, label):
    out = {r.name: {f: [] for f in FINDINGS} for r in readers}
    t0 = time.time()
    for i, img in enumerate(images):
        for r in readers:
            for f, v in r.scores(img).items():
                out[r.name][f].append(v)
        if i % 50 == 0:
            print(f"  {label} {i}/{len(images)}  {time.time() - t0:.0f}s", flush=True)
    return {r: {f: np.array(v) for f, v in per.items()} for r, per in out.items()}


def evaluate(result, source, scores, labels):
    for f, y in labels.items():
        entry = {}
        for reader, per in scores.items():
            s = per[f]
            entry[reader] = dict(auroc=round(float(roc_auc_score(y, s)), 3), n_pos=int(y.sum()), n_neg=int((1 - y).sum()), **thresholds(y, s))
        both = (scores["CLEAR"][f] + scores["CheXzero"][f]) / 2
        result["combined_auroc"][f] = round(float(roc_auc_score(y, both)), 3)
        result["source"][f] = source
        for reader, e in entry.items():
            result["readers"].setdefault(reader, {})[f] = e


def main():
    readers = [models.load_clear(), models.load_chexzero()]
    result = {"datasets": {"CheXpert": "CheXpert v1.0 validation, radiologist consensus, frontal views",
                           "NIH": "NIH ChestX-ray14 test split (2 shards), NLP-mined labels, sampled per finding"},
              "readers": {}, "combined_auroc": {}, "source": {}, "uncalibrated": [f for f in FINDINGS if f not in CHEXPERT and f not in NIH]}

    d = pd.read_parquet(DATA / "chexpert_valid.parquet")
    d = d[d["Frontal/Lateral"] == 0].reset_index(drop=True)
    imgs = [Image.open(io.BytesIO(b["bytes"])).convert("L") for b in d["image"]]
    print(f"CheXpert: {len(imgs)} frontal films")
    sc = score_all(readers, imgs, "CheXpert")
    evaluate(result, "CheXpert", sc, {f: (d[c].to_numpy() == 3).astype(int) for f, c in CHEXPERT.items()})

    nih = pd.concat([pd.read_parquet(p, columns=["image", "label_names", "view_position"]) for p in sorted(DATA.glob("nih_test_*.parquet"))])
    nih = nih[nih["view_position"].isin(["PA", "AP"])].reset_index(drop=True)
    rnd = random.Random(7)
    pick = set()
    for f, lab in NIH.items():
        pos = [i for i, names in enumerate(nih["label_names"]) if lab in list(names)]
        pick.update(rnd.sample(pos, min(NIH_POS_PER_FINDING, len(pos))))
    normals = [i for i, names in enumerate(nih["label_names"]) if len(names) == 0 or list(names) == ["No Finding"]]
    pick.update(rnd.sample(normals, min(NIH_NEGATIVES, len(normals))))
    sub = nih.iloc[sorted(pick)].reset_index(drop=True)
    imgs = [Image.open(io.BytesIO(b["bytes"])).convert("L") for b in sub["image"]]
    print(f"NIH: {len(imgs)} sampled films")
    sc = score_all(readers, imgs, "NIH")
    evaluate(result, "NIH", sc, {f: np.array([lab in list(n) for n in sub["label_names"]], dtype=int) for f, lab in NIH.items()})

    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT}\n")
    print(f"{'finding':<22}{'source':<10}{'pos':>5}  {'CLEAR':>6}  {'CheXzero':>8}  {'both':>6}")
    for f in FINDINGS:
        if f in result["source"]:
            a, b = result["readers"]["CLEAR"][f], result["readers"]["CheXzero"][f]
            print(f"{f:<22}{result['source'][f]:<10}{a['n_pos']:>5}  {a['auroc']:>6}  {b['auroc']:>8}  {result['combined_auroc'][f]:>6}")
        else:
            print(f"{f:<22}{'—':<10}  uncalibrated (no labels available)")


if __name__ == "__main__":
    main()
