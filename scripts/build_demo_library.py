"""Build a demo library: one folder per condition, each with its own NIH ChestX-ray14 film, a fictional patient-history PDF
and a current-presentation text. Films are pre-screened with CLEAR + CheXzero so each shows its condition clearly; no film
is used twice. Output goes to demo_data/ in the repository.

    PYTHONPATH=. .venv/bin/python scripts/build_demo_library.py
NIH ChestX-ray14: Wang et al., CVPR 2017 — unrestricted use with citation. Patients and records below are fictional.
"""
import io
import random
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from weasyprint import HTML

from bonaventure import models

DATA = Path.home() / "bonaventure/data"
OUT = Path(__file__).resolve().parent.parent / "demo_data"
CANDIDATES = 25
CSS = ("<style>body{font-family:'DejaVu Serif',serif;font-size:11pt;line-height:1.5} h1{font-size:15pt;border-bottom:1px solid #999}"
       " .pb{page-break-before:always} .hdr{color:#555;font-size:9pt}</style>")

# (folder, NIH label used to pick the film, finding that should score high, patient history HTML, presentation)
CASES = [
    ("01 Pleural effusion", "Effusion", "PLEURAL_EFFUSION", """
<div class=hdr>Riverside Oncology Centre</div><h1>ONCOLOGY CLINIC LETTER</h1>
<p>Patient: M. D'Souza, 71 F · Date: 14/08/2026</p>
<p>Diagnosis: Metastatic carcinoma of the right breast, diagnosed 2024, on second-line chemotherapy.</p>
<p>Known small right pleural effusion on staging CT in July 2026. Plan: review if breathlessness increases.</p>
<div class=pb></div><h1>RADIOLOGY REPORT — CT CHEST</h1><p>Date: 02 Jul 2026</p>
<p>Impression: Small right-sided pleural effusion. No pneumothorax.</p>""",
     "Increasingly short of breath for 5 days, worse on lying flat, sharp pain on the right side when breathing in. No fever."),
    ("02 Cardiomegaly", "Cardiomegaly", "CARDIOMEGALY", """
<div class=hdr>City Heart Institute</div><h1>CARDIOLOGY OUTPATIENT NOTE</h1>
<p>Patient: R. Kapoor, 64 M · Date: 03/09/2026</p>
<p>Diagnosis: Dilated cardiomyopathy, LVEF 30%. Hypertension since 2010.</p>
<p>Medications: furosemide 40 mg, sacubitril/valsartan, bisoprolol.</p>
<div class=pb></div><h1>ECHOCARDIOGRAM REPORT</h1><p>Date: 01/09/2026</p>
<p>Dilated left ventricle with global hypokinesia. Moderate mitral regurgitation.</p>""",
     "Tired all the time for 3 weeks, breathless on climbing one flight of stairs, both ankles swollen by evening."),
    ("03 Pulmonary edema", "Edema", "PULMONARY_EDEMA", """
<div class=hdr>St. Mary's Hospital</div><h1>DISCHARGE SUMMARY</h1>
<p>Patient: E. Thomas, 78 F · Date of discharge: 20/08/2026</p>
<p>Diagnosis: Acute decompensated congestive heart failure with fluid overload. Chronic kidney disease stage 3.</p>
<p>Medications at discharge: furosemide 80 mg twice daily, spironolactone 25 mg.</p>""",
     "Woke up gasping for breath last night, cannot lie flat, coughing frothy sputum, gained 3 kg in a week. No fever."),
    ("04 Pneumonia", "Consolidation", "CONSOLIDATION", """
<div class=hdr>Greenfield Family Practice</div><h1>PROGRESS NOTE</h1>
<p>Patient: A. Mensah, 45 M · Date: 10/06/2026</p>
<p>Type 2 diabetes, well controlled. Non-smoker. No previous lung disease.</p>
<p>Seen in 2025 for community-acquired pneumonia, treated with oral antibiotics, full recovery.</p>""",
     "Fever and shaking chills for 3 days, cough bringing up green sputum, sharp chest pain on breathing."),
    ("05 Atelectasis", "Atelectasis", "ATELECTASIS", """
<div class=hdr>Northside Surgical Unit</div><h1>OPERATION NOTE</h1>
<p>Patient: K. Nair, 59 M · Date: 05/10/2026</p>
<p>Procedure: Open right hemicolectomy under general anaesthesia. Post-operative day 2 at time of review.</p>
<p>Background: COPD, ex-smoker 30 pack-years.</p>""",
     "Post-operative day 2, shallow breathing because of wound pain, mild breathlessness, weak cough. Low-grade temperature."),
    ("06 Pneumothorax", "Pneumothorax", "PNEUMOTHORAX", """
<div class=hdr>University Health Service</div><h1>STUDENT HEALTH RECORD</h1>
<p>Patient: J. Fernandes, 22 M · Date: 12/01/2026</p>
<p>Tall, thin build. Smoker, 10 cigarettes a day. Previous right pneumothorax in 2024, managed with aspiration.</p>""",
     "Sudden sharp pain on the right side of the chest while studying an hour ago, now short of breath. No trauma."),
    ("07 Lung mass", "Mass", "LUNG_MASS", """
<div class=hdr>Regional Chest Clinic</div><h1>REFERRAL LETTER</h1>
<p>Patient: V. Raman, 67 M · Date: 22/09/2026</p>
<p>Heavy smoker, 45 pack-years. COPD. Occupational exposure to asbestos as a pipe-fitter.</p>
<p>Referred urgently for weight loss and haemoptysis.</p>""",
     "Coughing up streaks of blood for 2 weeks, lost 6 kg over 2 months without trying, persistent cough."),
    ("08 Emphysema", "Emphysema", "EMPHYSEMA", """
<div class=hdr>Breathe Easy Respiratory Clinic</div><h1>PULMONARY FUNCTION REPORT</h1>
<p>Patient: P. Gomes, 70 M · Date: 18/07/2026</p>
<p>Diagnosis: Severe COPD with emphysema. Smoker for 50 years (60 pack-years), quit 2023.</p>
<p>Spirometry: FEV1 38% predicted, markedly reduced gas transfer.</p>""",
     "Breathless for years, now breathless walking across the room, barrel chest, chronic morning cough."),
    ("09 Pulmonary fibrosis", "Fibrosis", "FIBROSIS", """
<div class=hdr>Interstitial Lung Disease Service</div><h1>CLINIC LETTER</h1>
<p>Patient: S. Menon, 66 F · Date: 09/08/2026</p>
<p>Diagnosis: Idiopathic pulmonary fibrosis (usual interstitial pneumonia pattern on HRCT, 2025). On antifibrotic therapy.</p>""",
     "Dry cough for over a year and slowly worsening breathlessness on exertion. Fingers have become clubbed."),
    ("10 Pleural thickening", "Pleural_Thickening", "PLEURAL_THICKENING", """
<div class=hdr>Occupational Health Department</div><h1>OCCUPATIONAL HISTORY</h1>
<p>Patient: G. Pereira, 72 M · Date: 30/05/2026</p>
<p>Worked 25 years as a shipyard insulator with heavy asbestos exposure. Pleural plaques noted on CT in 2022.</p>""",
     "Dull ache in the left chest for a few months, mild breathlessness on hills. No fever, no weight loss."),
    ("11 Hiatus hernia", "Hernia", "HERNIA", """
<div class=hdr>Digestive Health Clinic</div><h1>ENDOSCOPY REPORT</h1>
<p>Patient: L. Fonseca, 62 F · Date: 11/03/2026</p>
<p>Findings: Large sliding hiatus hernia. Grade B reflux oesophagitis. On omeprazole.</p>""",
     "Heartburn and acid reflux after meals for months, worse lying down, occasional fullness in the chest. Not breathless."),
    ("12 Lines and devices", None, "SUPPORT_DEVICES", """
<div class=hdr>Intensive Care Unit</div><h1>ICU ADMISSION NOTE</h1>
<p>Patient: N. Iqbal, 56 M · Date: 04/10/2026</p>
<p>Admitted with septic shock. Right internal jugular central venous catheter inserted 04/10/2026. Nasogastric tube in place.</p>""",
     "Ventilated ICU patient, check line position after central line insertion. Febrile."),
    ("13 Normal", "No Finding", None, """
<div class=hdr>Corporate Wellness Clinic</div><h1>PRE-EMPLOYMENT HEALTH CHECK</h1>
<p>Patient: T. Kurian, 30 F · Date: 01/10/2026</p>
<p>No significant past medical history. Non-smoker. No regular medications. Exercises three times a week.</p>""",
     "Routine pre-employment check, no symptoms. No cough, no fever, no breathlessness."),
    ("14 Pulmonary embolism (not on X-ray)", "No Finding", None, """
<div class=hdr>Lakeside Orthopaedic Hospital</div><h1>DISCHARGE SUMMARY</h1>
<p>Patient: H. Sharma, 52 F · Date of discharge: 25/09/2026</p>
<p>Procedure: Left total hip replacement on 20/09/2026. Mobility limited, walking with crutches.</p>
<p>Taking the combined oral contraceptive pill. Recent long-haul flight from Toronto on 15/09/2026.</p>""",
     "Sudden sharp chest pain when breathing in since this morning, heart racing, left calf swollen and tender. Fainted once."),
]


def main():
    nih = pd.concat([pd.read_parquet(p, columns=["image", "label_names", "view_position", "image_id"]) for p in sorted(DATA.glob("nih_test_*.parquet"))])
    nih = nih[nih["view_position"] == "PA"].reset_index(drop=True)
    labels = [list(x) for x in nih["label_names"]]
    readers = [models.load_clear(), models.load_chexzero()]
    rnd, used = random.Random(11), set()
    OUT.mkdir(parents=True, exist_ok=True)
    index = ["# Bonaventure demo library\n", "Fictional patients; films from NIH ChestX-ray14 (Wang et al., CVPR 2017).\n",
             "| Case | Film | NIH labels | Screening score |", "|---|---|---|---|"]

    def score(i, finding):
        img = Image.open(io.BytesIO(nih.at[i, "image"]["bytes"])).convert("L")
        s = [r.scores(img) for r in readers]
        if finding is None:  # normal: lowest worst-case score across every finding
            return -max(max(x.values()) for x in s), img
        return sum(x[finding] for x in s) / len(s), img

    for folder, label, finding, history, presentation in CASES:
        if label is None:   # no NIH label for devices: screen everything not yet used
            pool = [i for i in range(len(nih)) if i not in used]
        elif label == "No Finding":
            pool = [i for i, l in enumerate(labels) if (not l or l == ["No Finding"]) and i not in used]
        else:
            pool = [i for i, l in enumerate(labels) if l == [label] and i not in used]  # films carrying only this label
            if len(pool) < 5:
                pool = [i for i, l in enumerate(labels) if label in l and i not in used]
        pool = rnd.sample(pool, min(CANDIDATES if label else 80, len(pool)))
        best = max(pool, key=lambda i: score(i, finding)[0])
        used.add(best)
        val, img = score(best, finding)
        d = OUT / folder
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / "film.png")
        HTML(string=CSS + history).write_pdf(d / "history.pdf")
        (d / "presentation.txt").write_text(presentation + "\n")
        tags = ", ".join(labels[best]) or "No Finding"
        index.append(f"| {folder} | {nih.at[best, 'image_id']} | {tags} | {val:.3f} |")
        print(f"{folder:<40} {nih.at[best, 'image_id']:<20} {tags:<30} {val:.3f}", flush=True)
    (OUT / "README.md").write_text("\n".join(index) + "\n")
    print("\nwritten to", OUT)


if __name__ == "__main__":
    main()
