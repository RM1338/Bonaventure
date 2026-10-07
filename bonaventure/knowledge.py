"""Clinical vocabulary: concepts, their surface patterns, and which concepts bear on which finding."""

# concept id -> (display label, category, patterns). Patterns are regex fragments matched on word boundaries.
HISTORY_CONCEPTS = {
    "chf": ("Congestive heart failure", "Diagnosis", [r"congestive heart failure", r"heart failure", r"chf", r"hfref", r"hfpef", r"cardiac failure", r"lvef\s*(?:of\s*)?[1-3]\d\s*%"]),
    "cardiomyopathy": ("Cardiomyopathy", "Diagnosis", [r"\w*cardiomyopathy"]),
    "hypertension": ("Hypertension", "Diagnosis", [r"hypertension", r"htn"]),
    "valvular": ("Valvular heart disease", "Diagnosis", [r"mitral regurgitation", r"mitral stenosis", r"aortic stenosis", r"aortic regurgitation", r"valvular heart disease"]),
    "prior_effusion": ("Pleural effusion", "Imaging", [r"(?:\w+[- ]sided |bilateral |small |moderate |large )*pleural effusions?"]),
    "prior_cardiomegaly": ("Cardiomegaly", "Imaging", [r"cardiomegaly", r"enlarged (?:heart|cardiac silhouette)", r"cardiac enlargement"]),
    "prior_pneumothorax": ("Pneumothorax", "Imaging", [r"pneumothorax"]),
    "prior_edema": ("Pulmonary edema", "Imaging", [r"pulmonary o?edema", r"fluid overload", r"interstitial o?edema", r"(?:pulmonary )?venous congestion", r"upper lobe (?:venous )?diversion", r"kerley b lines?"]),
    "prior_atelectasis": ("Atelectasis", "Imaging", [r"atelectasis", r"lobar collapse"]),
    "pneumonia": ("Pneumonia", "Diagnosis", [r"pneumonia", r"lower respiratory tract infection", r"lrti"]),
    "copd": ("COPD / emphysema", "Diagnosis", [r"copd", r"emphysema", r"chronic obstructive"]),
    "malignancy": ("Malignancy", "Diagnosis", [r"\w*carcinoma", r"cancer", r"malignan\w*", r"metasta\w*", r"lymphoma"]),
    "renal_failure": ("Kidney disease", "Diagnosis", [r"chronic kidney disease", r"ckd", r"renal failure", r"esrd", r"dialysis"]),
    "trauma": ("Chest trauma", "Event", [r"chest trauma", r"rib fractures?", r"fell from", r"motor vehicle", r"road traffic accident", r"rta", r"blunt trauma"]),
    "recent_surgery": ("Recent surgery", "Procedure", [r"post-?operative", r"thoracotomy", r"laparotomy", r"cabg", r"surgery", r"underwent .{0,40}?(?:repair|resection|ectomy)"]),
    "procedure_line": ("Thoracic procedure / line", "Procedure", [r"central (?:venous )?(?:line|catheter)", r"thoracentesis", r"chest (?:tube|drain)", r"lung biopsy", r"pacemaker insertion"]),
    "diuretic": ("Diuretic therapy", "Medication", [r"furosemide", r"frusemide", r"lasix", r"torsemide", r"bumetanide", r"spironolactone"]),
    "immunosuppression": ("Immunosuppression", "Diagnosis", [r"hiv", r"chemotherapy", r"immunosuppress\w*", r"transplant"]),
    "smoker": ("Smoking history", "Risk factor", [r"(?<!non-)(?<!non )smoker", r"(?<!non-)smoking", r"pack[- ]years?"]),
    "ild": ("Interstitial lung disease", "Diagnosis", [r"interstitial lung disease", r"\bild\b", r"pulmonary fibrosis", r"\bipf\b", r"usual interstitial pneumonia"]),
    "asbestos": ("Asbestos exposure", "Risk factor", [r"asbestos\w*", r"pleural plaques?", r"mesothelioma"]),
    "prior_nodule": ("Lung nodule / mass", "Imaging", [r"(?:pulmonary |lung )?nodules?", r"(?:lung |pulmonary )mass(?:es)?", r"\bspn\b", r"lung lesion"]),
    "devices": ("Line / device in place", "Procedure", [r"central (?:venous )?(?:line|catheter)", r"picc", r"pacemaker", r"\bicd\b", r"endotracheal tube", r"nasogastric tube", r"chest (?:tube|drain)"]),
    "hiatus_hernia": ("Hiatus hernia", "Diagnosis", [r"hiatal hernia", r"hiatus hernia"]),
    "aneurysm": ("Aortic aneurysm", "Diagnosis", [r"aortic aneurysm", r"\btaa\b", r"marfan"]),
    "vte": ("Venous thromboembolism", "Diagnosis", [r"deep vein thrombosis", r"\bdvt\b", r"pulmonary embol\w*", r"\bvte\b", r"thromboembol\w*"]),
    "immobility": ("Recent immobility", "Risk factor", [r"immobili\w*", r"bed[- ]?bound", r"long[- ]haul flight", r"bed rest"]),
    "anticoagulant": ("Anticoagulation", "Medication", [r"warfarin", r"apixaban", r"rivaroxaban", r"dabigatran", r"enoxaparin", r"heparin"]),
}

SYMPTOM_CONCEPTS = {
    "dyspnea": ("Shortness of breath", [r"shortness of breath", r"short of breath", r"breathless(?:ness)?", r"dyspn(?:o)?ea", r"sob", r"difficulty (?:in )?breathing"]),
    "orthopnea": ("Orthopnea", [r"orthopn(?:o)?ea", r"(?:can'?t|cannot|unable to) lie flat", r"breathless (?:when|on) lying"]),
    "pnd": ("Night-time breathlessness", [r"paroxysmal nocturnal dyspn(?:o)?ea", r"pnd", r"wak\w* up (?:breathless|gasping)"]),
    "peripheral_edema": ("Ankle / leg swelling", [r"(?:ankle|leg|pedal|feet|foot) (?:swelling|o?edema)", r"swollen (?:ankles|legs|feet)", r"peripheral o?edema"]),
    "weight_gain": ("Recent weight gain", [r"weight gain", r"gained weight"]),
    "productive_cough": ("Productive cough", [r"productive cough", r"sputum", r"phlegm"]),
    "cough": ("Cough", [r"cough(?:ing)?"]),
    "fever": ("Fever", [r"fevers?", r"febrile", r"pyrexi\w*", r"chills", r"rigors"]),
    "pleuritic_pain": ("Pleuritic chest pain", [r"pleuritic", r"pain (?:on|when) (?:deep )?breathing", r"sharp chest pain"]),
    "chest_pain": ("Chest pain", [r"chest pain", r"chest tightness"]),
    "sudden_onset": ("Sudden onset", [r"sudden(?:ly)?", r"abrupt(?:ly)?"]),
    "trauma": ("Chest trauma", [r"chest trauma", r"trauma", r"injury", r"fell", r"fall", r"accident"]),
    "hemoptysis": ("Coughing blood", [r"ha?emoptysis", r"cough(?:ing)? (?:up )?blood"]),
    "fatigue": ("Fatigue", [r"fatigue", r"tiredness", r"tired"]),
    "weight_loss": ("Weight loss", [r"weight loss", r"lost weight", r"losing weight"]),
    "tachycardia": ("Fast heart rate", [r"tachycardi\w*", r"palpitations?", r"racing heart", r"heart (?:is )?racing", r"pounding heart", r"heart rate (?:of )?1[0-9]{2}"]),
    "calf_swelling": ("Calf pain / swelling", [r"calf (?:pain|swelling|tenderness)", r"swollen calf", r"unilateral leg swelling"]),
    "syncope": ("Fainting", [r"syncope", r"faint(?:ed|ing)?", r"collapsed?"]),
    "tearing_pain": ("Tearing chest / back pain", [r"tearing (?:chest |back )?pain", r"ripping pain", r"pain radiating to the back"]),
    "heartburn": ("Heartburn / reflux", [r"heartburn", r"reflux", r"\bgerd\b", r"dyspepsia"]),
    "suspected_pe": ("Suspected pulmonary embolism", [r"pulmonary embol\w*", r"\bpe\b", r"\bdvt\b", r"blood clot in (?:the )?lung"]),
}

# Phrases that state a normal result, i.e. explicit evidence *against* a history concept.
NORMAL_PHRASES = {
    "prior_cardiomegaly": [r"normal heart size", r"heart size (?:is )?(?:within normal limits|normal)", r"normal cardiac silhouette"],
    "prior_effusion": [r"costophrenic angles (?:are )?clear"],
    "prior_edema": [r"lungs (?:are )?clear"],
    "pneumonia": [r"lungs (?:are )?clear"],
}

# finding id -> display name, supporting history/symptom concepts, symptoms whose denial argues against it,
# and the zero-shot prompt pair used by the CLIP-style image models.
FINDINGS = {
    "PLEURAL_EFFUSION": dict(
        name="Pleural effusion", region="costophrenic angle",
        history=["prior_effusion", "chf", "malignancy", "renal_failure", "diuretic", "pneumonia"],
        symptoms=["dyspnea", "orthopnea", "pleuritic_pain"], key_against=[],
        prompts=("pleural effusion", "no pleural effusion")),
    "CARDIOMEGALY": dict(
        name="Cardiomegaly", region="cardiac silhouette",
        history=["prior_cardiomegaly", "chf", "cardiomyopathy", "hypertension", "valvular"],
        symptoms=["dyspnea", "orthopnea", "peripheral_edema", "fatigue"], key_against=[],
        prompts=("cardiomegaly", "no cardiomegaly")),
    "PNEUMOTHORAX": dict(
        name="Pneumothorax", region="apical pleural space",
        history=["prior_pneumothorax", "copd", "trauma", "procedure_line", "smoker"],
        symptoms=["sudden_onset", "pleuritic_pain", "chest_pain", "trauma", "dyspnea"], key_against=["trauma", "chest_pain"],
        prompts=("pneumothorax", "no pneumothorax")),
    "CONSOLIDATION": dict(
        name="Consolidation", region="lung parenchyma",
        history=["pneumonia", "immunosuppression", "copd"],
        symptoms=["fever", "productive_cough", "cough", "pleuritic_pain", "dyspnea"], key_against=["fever", "cough"],
        prompts=("consolidation", "no consolidation")),
    "PULMONARY_EDEMA": dict(
        name="Pulmonary edema", region="perihilar lung fields",
        history=["prior_edema", "chf", "renal_failure", "diuretic", "cardiomyopathy", "valvular"],
        symptoms=["dyspnea", "orthopnea", "pnd", "peripheral_edema", "weight_gain"], key_against=["dyspnea"],
        prompts=("pulmonary edema", "no pulmonary edema")),
    "ATELECTASIS": dict(
        name="Atelectasis", region="lung base",
        history=["prior_atelectasis", "recent_surgery", "malignancy", "copd"],
        symptoms=["dyspnea", "cough"], key_against=[],
        prompts=("atelectasis", "no atelectasis")),
}

# Beyond the original MVP six: the rest of the CheXpert / ChestX-ray14 label space, each calibrated on labelled data.
FINDINGS.update({
    "PNEUMONIA": dict(
        name="Pneumonia", region="lung parenchyma",
        history=["pneumonia", "immunosuppression", "copd"], symptoms=["fever", "productive_cough", "cough", "pleuritic_pain", "dyspnea"],
        key_against=["fever"], prompts=("pneumonia", "no pneumonia")),
    "LUNG_NODULE": dict(
        name="Lung nodule", region="lung field",
        history=["prior_nodule", "malignancy", "smoker"], symptoms=["hemoptysis", "weight_loss", "cough"], key_against=[],
        prompts=("lung nodule", "no lung nodule")),
    "LUNG_MASS": dict(
        name="Lung mass", region="lung field",
        history=["prior_nodule", "malignancy", "smoker", "asbestos"], symptoms=["hemoptysis", "weight_loss", "cough", "chest_pain"], key_against=[],
        prompts=("lung mass", "no lung mass")),
    "EMPHYSEMA": dict(
        name="Emphysema", region="both lungs",
        history=["copd", "smoker"], symptoms=["dyspnea", "cough"], key_against=[],
        prompts=("emphysema", "no emphysema")),
    "FIBROSIS": dict(
        name="Pulmonary fibrosis", region="lung bases",
        history=["ild", "asbestos"], symptoms=["dyspnea", "cough"], key_against=[],
        prompts=("pulmonary fibrosis", "no pulmonary fibrosis")),
    "PLEURAL_THICKENING": dict(
        name="Pleural thickening", region="pleura",
        history=["asbestos", "prior_effusion", "malignancy"], symptoms=["chest_pain", "dyspnea"], key_against=[],
        prompts=("pleural thickening", "no pleural thickening")),
    "ENLARGED_MEDIASTINUM": dict(
        name="Widened mediastinum", region="mediastinum",
        history=["aneurysm", "hypertension", "malignancy", "trauma"], symptoms=["tearing_pain", "chest_pain"], key_against=[],
        prompts=("enlarged cardiomediastinum", "normal cardiomediastinal silhouette")),
    "FRACTURE": dict(
        name="Rib fracture", region="ribs",
        history=["trauma"], symptoms=["trauma", "chest_pain", "pleuritic_pain"], key_against=["trauma"],
        prompts=("rib fracture", "no rib fracture")),
    "HERNIA": dict(
        name="Hiatus hernia", region="retrocardiac",
        history=["hiatus_hernia"], symptoms=["heartburn"], key_against=[],
        prompts=("hiatal hernia", "no hiatal hernia")),
    "SUPPORT_DEVICES": dict(
        name="Lines & devices", region="device course",
        history=["devices", "procedure_line"], symptoms=[], key_against=[], context_free=True,  # hardware, not disease
        prompts=("support devices, central line or pacemaker", "no support devices")),
})

# CheXpert-style label hierarchy: when the specific finding is raised, its broader / overlapping parent is redundant.
SUPPRESSED_BY = {"ENLARGED_MEDIASTINUM": "CARDIOMEGALY", "PNEUMONIA": "CONSOLIDATION"}

# Conditions a chest X-ray cannot rule in or out. When the context raises them, say so instead of guessing.
NOT_ASSESSABLE = {
    "PULMONARY_EMBOLISM": dict(
        name="Pulmonary embolism",
        triggers=dict(history=["vte", "immobility", "recent_surgery", "malignancy"], symptoms=["suspected_pe", "pleuritic_pain", "tachycardia", "calf_swelling", "hemoptysis", "syncope", "sudden_onset"]),
        min_triggers=2, direct=["suspected_pe", "vte"],
        advice="A chest X-ray can neither confirm nor exclude pulmonary embolism — most PE films are normal or non-specific. "
               "Consider a validated pre-test score (Wells / PERC), D-dimer and CT pulmonary angiography."),
    "AORTIC_DISSECTION": dict(
        name="Aortic dissection",
        triggers=dict(history=["aneurysm", "hypertension"], symptoms=["tearing_pain", "syncope"]),
        min_triggers=2, direct=["tearing_pain"],
        advice="A normal mediastinum on a chest X-ray does not exclude aortic dissection. CT aortography is the appropriate test."),
}

STATES = ("SUPPORTED", "UNCERTAIN", "CONFLICTING", "INSUFFICIENT_EVIDENCE")
