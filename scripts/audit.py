"""Hallucination / accuracy audit: run the FULL pipeline (all four models + reconciliation, no history, no presentation) on
NIH ChestX-ray14 films that were NOT used for calibration, and report what reached the screen.

    normals   : how often a normal film gets any finding (false positives) or any "also seen" (open-vocabulary false positives)
    diseased  : how often the labelled disease is raised (supported or uncertain) and how many unrelated findings ride along

    PYTHONPATH=. .venv/bin/python scripts/audit.py [n_normals] [n_per_label]
"""
import io
import json
import random
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd
from PIL import Image

from bonaventure import imaging, pipeline
from scripts.calibrate import DATA, NIH, NIH_NEGATIVES, NIH_POS_PER_FINDING

LABEL_TO_FINDING = {"Effusion": "PLEURAL_EFFUSION", "Cardiomegaly": "CARDIOMEGALY", "Edema": "PULMONARY_EDEMA", "Consolidation": "CONSOLIDATION",
                    "Atelectasis": "ATELECTASIS", "Pneumothorax": "PNEUMOTHORAX", "Pneumonia": "PNEUMONIA", "Mass": "LUNG_MASS", "Nodule": "LUNG_NODULE",
                    "Emphysema": "EMPHYSEMA", "Fibrosis": "FIBROSIS", "Pleural_Thickening": "PLEURAL_THICKENING", "Hernia": "HERNIA"}
OUT = Path(__file__).resolve().parent.parent / "bonaventure" / "audit.json"


def calibration_rows(nih):
    """Re-draw the calibration sample exactly as scripts/calibrate.py did, so the audit uses unseen films."""
    rnd, pick = random.Random(7), set()
    for f, lab in NIH.items():
        pos = [i for i, names in enumerate(nih["label_names"]) if lab in list(names)]
        pick.update(rnd.sample(pos, min(NIH_POS_PER_FINDING, len(pos))))
    normals = [i for i, names in enumerate(nih["label_names"]) if len(names) == 0 or list(names) == ["No Finding"]]
    pick.update(rnd.sample(normals, min(NIH_NEGATIVES, len(normals))))
    return pick


def main(n_normals=12, n_per_label=2):
    nih = pd.concat([pd.read_parquet(p, columns=["image", "label_names", "view_position", "image_id"]) for p in sorted(DATA.glob("nih_test_*.parquet"))])
    nih = nih[nih["view_position"].isin(["PA", "AP"])].reset_index(drop=True)
    seen = calibration_rows(nih)
    labels = [list(x) for x in nih["label_names"]]
    rnd = random.Random(2026)
    films = [(i, None) for i in rnd.sample([i for i, l in enumerate(labels) if (not l or l == ["No Finding"]) and i not in seen and nih.at[i, "view_position"] == "PA"], n_normals)]
    for lab in LABEL_TO_FINDING:
        pool = [i for i, l in enumerate(labels) if l == [lab] and i not in seen]
        films += [(i, lab) for i in rnd.sample(pool, min(n_per_label, len(pool)))]

    eng = imaging.ImagingEngine()
    while not eng.ready():
        time.sleep(0.5)
    tmp = Path(tempfile.mkdtemp())
    rows = []
    for k, (i, lab) in enumerate(films):
        p = tmp / f"{Path(nih.at[i, 'image_id']).stem}.png"
        Image.open(io.BytesIO(nih.at[i, "image"]["bytes"])).save(p)
        c = pipeline.Case({"path": str(p), "name": p.name}, [], "")
        c.run(eng)
        r = c.result or {}
        raised = {f["canonical_name"]: f["status"] for f in r.get("findings", []) if f["status"] in ("SUPPORTED", "UNCERTAIN", "CONFLICTING")}
        target = LABEL_TO_FINDING.get(lab)
        rows.append(dict(image=nih.at[i, "image_id"], label=lab or "Normal", target=target, raised=raised,
                         supported=[f for f, s in raised.items() if s == "SUPPORTED"], hit=bool(target and target in raised),
                         also_seen=[o["name"] for o in r.get("other_observations", [])], rejected=len(r.get("rejected", [])), case=c.id))
        print(f"[{k + 1}/{len(films)}] {lab or 'Normal':<18} raised={raised}  also={rows[-1]['also_seen']}  rejected={rows[-1]['rejected']}", flush=True)

    normals = [r for r in rows if r["label"] == "Normal"]
    diseased = [r for r in rows if r["label"] != "Normal"]
    summary = dict(
        n_normals=len(normals),
        normals_with_supported_finding=sum(bool(r["supported"]) for r in normals),
        normals_with_any_finding=sum(bool(r["raised"]) for r in normals),
        normals_with_also_seen=sum(bool(r["also_seen"]) for r in normals),
        n_diseased=len(diseased),
        disease_raised=sum(r["hit"] for r in diseased),
        mean_extra_findings=round(sum(len(set(r["raised"]) - {r["target"]}) for r in diseased) / max(len(diseased), 1), 2),
        claims_rejected_total=sum(r["rejected"] for r in rows),
        by_label={lab: [r["hit"] for r in diseased if r["label"] == lab] for lab in LABEL_TO_FINDING},
    )
    OUT.write_text(json.dumps(dict(summary=summary, rows=rows), indent=2))
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:3]))
