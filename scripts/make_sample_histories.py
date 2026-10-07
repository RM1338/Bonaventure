"""Generate the synthetic patient-history PDFs used by the demo cases (fictional patients)."""
from pathlib import Path
from weasyprint import HTML

OUT = Path(__file__).resolve().parent.parent / "sample_data" / "histories"
CSS = "<style>body{font-family:'DejaVu Serif',serif;font-size:11pt;line-height:1.5} h1{font-size:15pt;border-bottom:1px solid #999} .pb{page-break-before:always} .hdr{color:#555;font-size:9pt}</style>"

DOCS = {
    "case_a_history.pdf": """
<div class=hdr>St. Bonaventure General Hospital · Department of Cardiology</div>
<h1>DISCHARGE SUMMARY</h1>
<p>Patient: R. Menon, 67 M · MRN 0042117<br>Date of admission: 26/07/2026 · Date of discharge: 30/07/2026</p>
<p>Diagnosis: Acute decompensated congestive heart failure (HFrEF, LVEF 30%). Background of hypertension since 2012 and type 2 diabetes.</p>
<p>Course: Admitted with breathlessness and bilateral ankle oedema. Treated with intravenous diuretics with good response.</p>
<p>Discharge medications: Furosemide 40 mg once daily, ramipril 5 mg, bisoprolol 2.5 mg, metformin 500 mg twice daily.</p>
<p>Follow-up: Heart failure clinic in 4 weeks. Return if weight gain over 2 kg or worsening breathlessness.</p>
<div class=pb></div>
<h1>ECHOCARDIOGRAM REPORT</h1>
<p>Date: 28/07/2026</p>
<p>Dilated left ventricle with global hypokinesia. Ischaemic cardiomyopathy. LVEF 30%. Moderate mitral regurgitation. No pericardial effusion.</p>
<div class=pb></div>
<h1>RADIOLOGY REPORT — CHEST X-RAY PA</h1>
<p>Date: 12 Aug 2026</p>
<p>Findings: The cardiac silhouette is enlarged. Upper lobe venous diversion. Small right-sided pleural effusion.</p>
<p>Impression: Cardiomegaly with features of pulmonary venous congestion. Small right pleural effusion. No pneumothorax. No focal consolidation.</p>
""",
    "case_b_history.pdf": """
<div class=hdr>Riverside Family Practice</div>
<h1>PROGRESS NOTE</h1>
<p>Patient: A. Fernandes, 34 F · Date: 02/09/2026</p>
<p>Annual review. No history of heart failure. No previous lung disease. Non-smoker.</p>
<p>Examination unremarkable. Chest clear on auscultation. No peripheral oedema.</p>
<div class=pb></div>
<h1>RADIOLOGY REPORT — CHEST X-RAY PA</h1>
<p>Date: 02 Sep 2026</p>
<p>Impression: Normal heart size. Lungs clear. No pleural effusion. No pneumothorax.</p>
""",
    "case_d_history.pdf": """
<div class=hdr>St. Bonaventure General Hospital · Orthopaedics</div>
<h1>DISCHARGE SUMMARY</h1>
<p>Patient: S. Iyer, 58 F · MRN 0051930<br>Date of admission: 18/09/2026 · Date of discharge: 23/09/2026</p>
<p>Procedure: Right total knee replacement on 19/09/2026. Uncomplicated post-operative course.</p>
<p>Mobility: limited, walking with frame. Thromboprophylaxis stopped at discharge. Background: type 2 diabetes. Non-smoker.</p>
<div class=pb></div>
<h1>RADIOLOGY REPORT — CHEST X-RAY PA</h1>
<p>Date: 18 Sep 2026 (pre-operative)</p>
<p>Impression: Normal heart size. Lungs clear. No pleural effusion.</p>
""",
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in DOCS.items():
        HTML(string=CSS + body).write_pdf(OUT / name)
        print("wrote", OUT / name)
