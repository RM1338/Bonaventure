"""Real imaging models. Imported lazily by imaging.ImagingEngine so the UI starts without torch.

primary       CLEAR (DINOv2 ViT-B/14 + text encoder): zero-shot prompt pairs + retrieval over its 368,294-concept bank
verifier      CheXzero (CLIP ViT-B/32, MIMIC-CXR): same prompt pairs, independently trained
reasoning     MedGemma 1.5 4B (4-bit): describes and boxes the candidates the image models raised
segmentation  MedSAM (SAM ViT-B, medical): turns each box into a mask; its outline is what the UI draws
"""
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")  # less fragmentation across cases on a 6 GB GPU
import torch  # noqa: E402

from .knowledge import FINDINGS, SUPPRESSED_BY
from .pipeline import ROOT

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# 6 GB budget: MedGemma (4-bit) + MedSAM's 1024px encoder own the GPU; the two CLIP-style readers are quick enough on CPU
CLIP_DEVICE = os.environ.get("BV_CLIP_DEVICE", "cpu")
_LOCAL_CLEAR_DIR = ROOT / "models/clear"
CLEAR_DIR = Path(os.environ.get("BV_CLEAR_DIR", _LOCAL_CLEAR_DIR if _LOCAL_CLEAR_DIR.is_dir() else Path.home() / "bonaventure/models/clear"))
CLEAR_CKPT = os.environ.get("BV_CLEAR_CKPT") or (str(CLEAR_DIR / "best_model.pt") if (CLEAR_DIR / "best_model.pt").exists() else None)
_LOCAL_TORCH_HOME = ROOT / "models/.torch-cache"
if (_LOCAL_TORCH_HOME / "hub/facebookresearch_dinov2_main/hubconf.py").is_file():
    os.environ.setdefault("TORCH_HOME", str(_LOCAL_TORCH_HOME))
MEDSAM_DIR = ROOT / "models/MedSAM" if (ROOT / "models/MedSAM").is_dir() else ROOT / "MedSAM"
CHEXZERO_DIR = ROOT / "models/CheXzero" if (ROOT / "models/CheXzero").is_dir() else ROOT / "CheXzero"
MEDSAM_CKPT = MEDSAM_DIR / "work_dir/MedSAM/medsam_vit_b.pth"
CHEXZERO_CKPT = CHEXZERO_DIR / "checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt"
_LOCAL_MEDGEMMA = Path.home() / "bonaventure/models/medgemma-1.5-4b-it"
MEDGEMMA_ID = os.environ.get("BV_MEDGEMMA") or (str(_LOCAL_MEDGEMMA) if (_LOCAL_MEDGEMMA / "model-00002-of-00002.safetensors").exists() else "google/medgemma-1.5-4b-it")
CALIBRATION = Path(__file__).resolve().parent / "calibration.json"   # scripts/calibrate.py on CheXpert validation


def _thresholds():
    """{reader: {finding: [weak, moderate, strong]}} from the CheXpert calibration; hand-set fallback if it is missing."""
    fallback = {"CLEAR": [0.8, 0.9, 0.95], "CheXzero": [0.5, 0.7, 0.85]}
    if not CALIBRATION.exists():
        return {r: {f: t for f in FINDINGS} for r, t in fallback.items()}
    cal = json.loads(CALIBRATION.read_text())["readers"]
    out = {}
    for reader, per in cal.items():
        out[reader] = {f: fallback[reader] for f in FINDINGS}  # findings with no labelled data (rib fracture) keep hand-set levels
        for f, c in per.items():
            w, m, st = c["thresholds"]
            # too few positives (pneumothorax: 7) to trust a ROC point: keep the stricter hand-set levels for that finding
            out[reader][f] = fallback[reader] if c["n_pos"] < 15 else [w, m, st]
    return out


THRESHOLDS = _thresholds()
MIN_AUROC = 0.70  # a reader only votes on findings it could actually separate on labelled data


def _reliable():
    """{reader: {finding: bool}} — True only where the reader reached MIN_AUROC in calibration (uncalibrated -> False)."""
    if not CALIBRATION.exists():
        return {r: {f: True for f in FINDINGS} for r in ("CLEAR", "CheXzero")}
    cal = json.loads(CALIBRATION.read_text())["readers"]
    return {r: {f: per.get(f, {}).get("auroc", 0) >= MIN_AUROC for f in FINDINGS} for r, per in cal.items()}


RELIABLE = _reliable()
CONCEPT_CAL = Path(__file__).resolve().parent / "concept_calibration.json"   # scripts/eval_concepts.py


def _concept_reader():
    """{finding: {reliable, strong, moderate, weak}} — concept-bank rank cut-offs measured on labelled films."""
    if not CONCEPT_CAL.exists():
        return {}
    cal = json.loads(CONCEPT_CAL.read_text())
    return {f: dict(reliable=c["auroc"] >= MIN_AUROC, auroc=c["auroc"], strong=c["rank_at_90_spec"],
                    moderate=max(c["rank_at_youden"], c["rank_at_90_spec"]), weak=max(c["rank_at_90_sens"], c["rank_at_youden"]))
            for f, c in cal.items()}


CONCEPT_READER = _concept_reader()
OPEN_VOCAB_MIN = 0.85  # CLEAR's prompt-pair probabilities run high, so an open-vocabulary claim must clear a high bar
MAX_LOCALIZE = 3  # ~3 s of MedGemma per box on an RTX 3050


def _import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------- CLIP-style zero-shot ----------

class ZeroShot:
    def __init__(self, name, model, preprocess, tokenize):
        self.name, self.model, self.preprocess = name, model, preprocess
        with torch.inference_mode():
            pos = [FINDINGS[f]["prompts"][0] for f in FINDINGS]
            neg = [FINDINGS[f]["prompts"][1] for f in FINDINGS]
            t = model.encode_text(tokenize(pos + neg).to(CLIP_DEVICE)).float()
            t = t / t.norm(dim=-1, keepdim=True)
            self.pos, self.neg = t[: len(pos)], t[len(pos):]
        self.scale = float(model.logit_scale.exp().detach()) if hasattr(model, "logit_scale") else 100.0

    @torch.inference_mode()
    def scores(self, img):
        x = self.preprocess(img).unsqueeze(0).to(CLIP_DEVICE)
        f = self.model.encode_image(x.to(next(self.model.parameters()).dtype)).float()
        f = f / f.norm(dim=-1, keepdim=True)
        self.last_features = f[0]
        # softmax over the (positive, negative) prompt pair == sigmoid of the scaled similarity gap
        p = torch.sigmoid(self.scale * ((f @ self.pos.T) - (f @ self.neg.T)))[0]
        return {fid: float(v) for fid, v in zip(FINDINGS, p)}


    @torch.inference_mode()
    def check(self, phrases, tokenize):
        """Open-vocabulary second read of the last image: P(phrase) vs P('no ' + phrase) for each phrase."""
        if not phrases:
            return []
        t = self.model.encode_text(tokenize([p.lower() for p in phrases] + [f"no {p.lower()}" for p in phrases]).to(CLIP_DEVICE)).float()
        t = t / t.norm(dim=-1, keepdim=True)
        pos, neg = t[: len(phrases)], t[len(phrases):]
        f = self.last_features
        return torch.sigmoid(self.scale * ((pos @ f) - (neg @ f))).tolist()


def load_clear():
    sys.path.insert(0, str(ROOT / "CLEAR/src"))
    import clear
    model, preprocess = clear.load_pretrained(CLEAR_CKPT, device=CLIP_DEVICE, local_files_only=True)
    zs = ZeroShot("CLEAR", model, preprocess, clear.tokenize)
    zs.tokenize = clear.tokenize
    return zs


def load_chexzero():
    from torchvision.transforms import Compose, InterpolationMode, Lambda, Normalize, Resize
    cz_dir = CHEXZERO_DIR
    sys.path.insert(0, str(cz_dir))
    cz_model = _import_file("chexzero_model", cz_dir / "model.py")
    cz_clip = _import_file("chexzero_clip", cz_dir / "clip.py")
    # released checkpoints are fine-tuned OpenAI ViT-B/32 CLIP: infer the architecture from the state dict itself
    model = cz_model.build_model(torch.load(CHEXZERO_CKPT, map_location="cpu")).float().to(CLIP_DEVICE).eval()
    res = model.visual.input_resolution

    def preprocess(img):  # CheXzero: aspect-preserving resize + zero-pad to 320, raw 0-255 normalised with CXR stats
        g = img.convert("L")
        r = 320 / max(g.size)
        g = g.resize((max(1, round(g.width * r)), max(1, round(g.height * r))), 3)
        from PIL import Image
        canvas = Image.new("L", (320, 320))
        canvas.paste(g, ((320 - g.width) // 2, (320 - g.height) // 2))
        t = torch.from_numpy(np.asarray(canvas, dtype=np.float32))[None].repeat(3, 1, 1)
        t = Normalize((101.48761,) * 3, (83.43944,) * 3)(t)
        return Resize(res, interpolation=InterpolationMode.BICUBIC, antialias=True)(t) if res != 320 else t

    return ZeroShot("CheXzero", model, preprocess, lambda texts: cz_clip.tokenize(texts, context_length=77))


# ---------- CLEAR concept bank: which radiological observations does the film look like? ----------

# radiological phrases that bear on each finding (a concept containing one of these is evidence for or against it)
CONCEPT_TERMS = {
    "PLEURAL_EFFUSION": r"pleural effusion|effusions?\b|blunting of the (?:right |left )?costophrenic",
    "CARDIOMEGALY": r"cardiomegaly|\bchf\b|congestive heart failure|cardiomyopathy|(?:heart|cardiac silhouette|cardiac size|heart size|cardiomediastinal silhouette)\b.{0,25}\b(?:enlarged|enlargement|large|top[- ]normal|normal)|enlarge\w* (?:heart|cardiac)",
    "PNEUMOTHORAX": r"pneumothora",
    "CONSOLIDATION": r"consolidation|airspace (?:opacit|disease)|pneumonia",
    "PULMONARY_EDEMA": r"edema|vascular congestion|kerley|interstitial markings|cephalization",
    "ATELECTASIS": r"atelecta|collapse|volume loss",
    "PNEUMONIA": r"pneumonia|infectio",
    "LUNG_NODULE": r"nodul",
    "LUNG_MASS": r"\bmass\b|tumou?r|neoplasm|malignan",
    "EMPHYSEMA": r"emphysema|hyperinflat|bullae|bullous",
    "FIBROSIS": r"fibros|fibrotic|reticul|honeycomb|interstitial lung disease",
    "PLEURAL_THICKENING": r"pleural thickening|pleural plaque|apical (?:cap|thickening)",
    "ENLARGED_MEDIASTINUM": r"(?:widen|enlarg)\w* (?:superior )?mediastin|mediastinal widening|enlarged cardiomediastinal|tortuous aorta|aortic (?:knob|knuckle) (?:is )?(?:prominent|enlarged)",
    "FRACTURE": r"fracture",
    "HERNIA": r"hiatal hernia|hiatus hernia|hernia",
    "SUPPORT_DEVICES": r"catheter|\bline\b|pacemaker|pacer|\bicd\b|tube|lead|port|sternotomy wires|clips",
}
_NEGATIVE = re.compile(r"^(?:no|without|resolved|resolution of|negative for)\b|\bnormal\b|\bno (?:new|evidence|definite|focal|large|significant)\b", re.I)


_NEG_BEFORE = re.compile(r"\b(?:no|without|resolved|resolution of|negative for|free of|absent|clear of|not)\b[^,;.]*$", re.I)


def concept_negated(text, pos):
    """'bilateral chest tube without visible pneumothorax' negates pneumothorax: look for a negation earlier in the clause."""
    return bool(_NEGATIVE.match(text)) and pos < 25 or bool(_NEG_BEFORE.search(text[:pos]))


class ConceptBank:
    """Rank all 368,294 CLEAR concepts against the film and keep the ones that speak to each finding."""

    def __init__(self, clear_model):
        import csv
        emb = torch.load(CLEAR_DIR / "concept_embeddings_368294.pt", map_location="cpu", weights_only=True)
        self.emb = torch.nn.functional.normalize(emb.float(), dim=-1).half()   # CPU, fp16: ~565 MB RAM, no VRAM
        with open(CLEAR_DIR / "mimic_concepts.csv", newline="", encoding="utf-8") as fh:
            self.text = [row["concept"] for row in csv.DictReader(fh)]
        assert len(self.text) == self.emb.shape[0], "concept list and embeddings disagree"
        self.rx = {f: re.compile(t, re.I) for f, t in CONCEPT_TERMS.items()}

    @torch.inference_mode()
    def explain(self, features, top_k=2500, per_finding=3):
        sims = (self.emb @ features.detach().cpu().half()).float()
        top = torch.topk(sims, top_k)
        ranked = [(self.text[i], int(r) + 1, round(float(v), 4)) for r, (v, i) in enumerate(zip(top.values, top.indices.tolist()))]
        out = {}
        for fid, rx in self.rx.items():
            pos, neg = [], []
            for c in ranked:
                m = rx.search(c[0])
                if m:
                    (neg if concept_negated(c[0], m.start()) else pos).append(c)
            out[fid] = {"for": pos[:per_finding], "against": neg[:per_finding]}
        return out, ranked[:10]


# ---------- MedSAM: box prompt -> mask -> outline ----------

class MedSAM:
    def __init__(self):
        sys.path.insert(0, str(MEDSAM_DIR))
        from segment_anything import sam_model_registry
        self.model = sam_model_registry["vit_b"](checkpoint=str(MEDSAM_CKPT)).to(DEVICE).eval()

    @torch.inference_mode()
    def outline(self, img, boxes):
        """boxes: {FINDING: [x0,y0,x1,y1] 0-1} -> {FINDING: [[x,y], ...] 0-1 closed outline} (skips empty / runaway masks)."""
        import torch.nn.functional as F
        g = np.asarray(img.convert("L").resize((1024, 1024), 3), dtype=np.float32)
        g = (g - g.min()) / max(g.max() - g.min(), 1e-8)
        x = torch.from_numpy(np.repeat(g[None], 3, 0))[None]
        try:
            if DEVICE == "cuda":
                torch.cuda.empty_cache()  # MedGemma's generation leaves cached blocks; the 1024px encoder needs them
            with torch.autocast(DEVICE, dtype=torch.float16, enabled=DEVICE == "cuda"):
                emb = self.model.image_encoder(x.to(DEVICE))
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            print("[models] MedSAM: GPU full, segmenting on CPU (~9 s)")
            self.model.cpu()
            emb = self.model.image_encoder(x)
        dev = emb.device
        out = {}
        for fid, b in boxes.items():
            box = torch.tensor([[b[0] * 1024, b[1] * 1024, b[2] * 1024, b[3] * 1024]], dtype=torch.float, device=dev)[:, None, :]
            sparse, dense = self.model.prompt_encoder(points=None, boxes=box, masks=None)
            logits, _ = self.model.mask_decoder(image_embeddings=emb.float(), image_pe=self.model.prompt_encoder.get_dense_pe(),
                                                sparse_prompt_embeddings=sparse, dense_prompt_embeddings=dense, multimask_output=False)
            mask = (torch.sigmoid(F.interpolate(logits, size=(256, 256), mode="bilinear", align_corners=False))[0, 0] > 0.5).cpu().numpy()
            area, box_area = mask.mean(), (b[2] - b[0]) * (b[3] - b[1])
            if 0.08 * box_area < area < 1.6 * box_area:
                out[fid] = mask_outline(mask)
        del emb
        if DEVICE == "cuda":
            self.model.to(DEVICE)
            torch.cuda.empty_cache()
        return out


def mask_outline(mask, rays=72):
    """Star-shaped outline of the largest blob: furthest mask pixel along rays from the centroid (no OpenCV needed)."""
    ys, xs = np.nonzero(mask)
    cy, cx = ys.mean(), xs.mean()
    h, w = mask.shape
    pts = []
    for a in np.linspace(0, 2 * np.pi, rays, endpoint=False):
        r = np.arange(0, max(h, w), 0.75)
        px, py = (cx + r * np.cos(a)).astype(int), (cy + r * np.sin(a)).astype(int)
        ok = (px >= 0) & (px < w) & (py >= 0) & (py < h)
        px, py = px[ok], py[ok]
        inside = np.nonzero(mask[py, px])[0]
        k = inside[-1] if len(inside) else 0
        pts.append([round(float(px[k]) / w, 4), round(float(py[k]) / h, 4)])
    return pts


# ---------- MedGemma localization + observations ----------

class MedGemma:
    def __init__(self):
        from transformers import AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig
        self.processor = AutoProcessor.from_pretrained(MEDGEMMA_ID)
        self.model = AutoModelForImageTextToText.from_pretrained(
            MEDGEMMA_ID, device_map={"": 0} if DEVICE == "cuda" else None, dtype=torch.bfloat16,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16) if DEVICE == "cuda" else None)
        self.model.eval()

    DESCRIBE = (
        "You are assisting a radiologist reviewing a frontal chest X-ray. For each candidate finding listed, decide whether it is "
        "visible on this image. Give a short anatomical region (e.g. 'right costophrenic angle') and up to 2 brief radiological "
        "observations that support it. Do not report findings that are not listed. Answer with JSON only, in this form:\n"
        '{{"findings": [{{"name": "<finding>", "visible": true, "region": "<region>", "observations": ["<observation>"]}}]}}\n'
        "Candidate findings: {names}"
    )
    SURVEY = ("You are assisting a radiologist. List every abnormal finding visible on this frontal chest X-ray, including lines, "
              "tubes and devices. Be specific (e.g. 'right upper lobe mass', 'left-sided central venous catheter', 'elevated right "
              "hemidiaphragm'). Do not list normal structures. Answer with JSON only: "
              '{"findings": [{"name": "<finding>", "region": "<region>"}]} — an empty list if the film is normal.')
    LOCATE = ('Locate the {name} on this chest X-ray. Output the bounding box as JSON: '
              '[{{"box_2d": [y_min, x_min, y_max, x_max], "label": "{name}"}}] with coordinates normalized to 0-1000.')

    def _ask(self, img, text, max_new_tokens):
        messages = [{"role": "user", "content": [{"type": "image", "image": img.convert("RGB")}, {"type": "text", "text": text}]}]
        inputs = self.processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True,
                                                    return_tensors="pt").to(self.model.device, dtype=torch.bfloat16)
        out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        return self.processor.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)

    @torch.inference_mode()
    def describe(self, img, finding_ids):
        text = self._ask(img, self.DESCRIBE.format(names=", ".join(FINDINGS[f]["name"] for f in finding_ids)), 120 * len(finding_ids) + 80)
        return parse_medgemma(text, finding_ids), text

    @torch.inference_mode()
    def survey(self, img):
        text = self._ask(img, self.SURVEY, 300)
        return parse_survey(text), text

    @torch.inference_mode()
    def rewrite_clinical(self, clauses):
        """Translate each phrase of a natural note into standard clinical wording (negation kept, nothing added).
        The deterministic parser reads the rewrites, so concept mapping stays rule-based and every concept keeps its source phrase."""
        numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(clauses, 1))
        prompt = ("Rewrite each numbered phrase from a clinician's note in plain standard clinical terms, keeping any negation. "
                  "Examples: 'gets winded on the stairs' -> 'shortness of breath on exertion'; 'sleeps propped up on pillows' -> "
                  "'orthopnea, cannot lie flat'; 'no temperature' -> 'no fever'; 'heart pounding' -> 'palpitations, racing heart'. "
                  "Do not add anything that is not in the phrase. Reply with the same numbers, one line each.\n" + numbered)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        chat = self.processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False) + "1."  # skip any 'thinking'
        inputs = self.processor(text=chat, return_tensors="pt").to(self.model.device)
        out = self.model.generate(**inputs, max_new_tokens=24 * len(clauses) + 20, do_sample=False)
        reply = "1." + self.processor.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
        rewrites = {}
        for line in reply.splitlines():
            m = re.match(r"\s*(\d+)\.\s*(.+)", line)
            if m and 1 <= int(m.group(1)) <= len(clauses):
                rewrites[int(m.group(1)) - 1] = m.group(2).strip()
        return [rewrites.get(i, "") for i in range(len(clauses))], reply

    @torch.inference_mode()
    def second_look(self, img, finding_id, verdict, note):
        """A clinician disagrees: look again, given their reasoning. One model's opinion, shown as such."""
        name = FINDINGS[finding_id]["name"].lower()
        claim = f"there is no {name}" if verdict == "absent" else f"there is {name}"
        text = self._ask(img, (f"A clinician reviewing this chest X-ray believes {claim}. Their reasoning: \"{note or 'not given'}\". "
                               f"Look again carefully. Is {name} visible? Answer with JSON only: "
                               '{"visible": true or false, "reason": "<one sentence naming what you see and where>"}'), 120)
        m = re.search(r"\{.*?\}", text, re.S)
        try:
            out = json.loads(m.group(0))
            return dict(visible=bool(out.get("visible")), reason=str(out.get("reason", "")).strip() or "no reason given")
        except (AttributeError, json.JSONDecodeError):
            return None

    @torch.inference_mode()
    def locate(self, img, finding_id):
        text = self._ask(img, self.LOCATE.format(name=FINDINGS[finding_id]["name"].lower()), 80)
        return parse_box(text), text


def parse_medgemma(text, finding_ids):
    """Tolerant JSON extraction -> {FINDING: {visible, bbox [x0,y0,x1,y1] 0-1, region, observations}}."""
    by_name = {FINDINGS[f]["name"].lower(): f for f in finding_ids}
    items, dec, i = [], json.JSONDecoder(), 0
    while (i := text.find("{", i)) != -1:  # the model may emit one object per finding, so decode every object
        try:
            obj, end = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict) and isinstance(obj.get("findings"), list):
            items += [x for x in obj["findings"] if isinstance(x, dict)]
        elif isinstance(obj, dict) and "name" in obj and "visible" in obj:
            items.append(obj)  # a complete finding inside a reply that was cut off before its closing brackets
        i = end
    out = {}
    for it in items:
        name = str(it.get("name", "")).lower()
        fid = by_name.get(name) or next((f for n, f in by_name.items() if n in name or name in n), None)
        if not fid:
            continue
        out[fid] = dict(visible=bool(it.get("visible", True)), region=str(it.get("region") or "").strip() or None,
                        observations=[str(o) for o in (it.get("observations") or [])][:2])
    return out


def parse_survey(text):
    """MedGemma's open-ended list -> [{name, region, maps_to}] where maps_to is a catalogue finding or None."""
    items, dec = [], json.JSONDecoder()
    for i, ch in enumerate(text):  # the model answers either {"findings": [...]} or a bare [...]
        if ch not in "[{":
            continue
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        rows = obj.get("findings") if isinstance(obj, dict) else obj
        if isinstance(rows, list) and rows and all(isinstance(x, dict) for x in rows):
            items = [x for x in rows if x.get("name")]
            break
    out, seen = [], set()
    for it in items:
        name = str(it["name"]).strip()
        hedged = re.match(r"(?:possible|probable|questionable|suspected|\?)\b", name, re.I)
        if name.lower() in seen or hedged or re.search(r"\bno\b|normal|unremarkable|clear lungs", name, re.I):
            continue
        seen.add(name.lower())
        maps = next((f for f, t in CONCEPT_TERMS.items() if re.search(t, name, re.I)), None)
        out.append(dict(name=name[0].upper() + name[1:], region=str(it.get("region") or "").strip() or None, maps_to=maps, source="MedGemma 1.5"))
    return out


def ground_concepts(reply, text, symptom_ids, history_ids):
    """Keep only concepts whose quote really occurs in the clinician's text (case-insensitive); everything else is discarded."""
    m = re.search(r"\[.*\]", reply, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        items = []
    from .knowledge import HISTORY_CONCEPTS, SYMPTOM_CONCEPTS
    by_label = {v[0].lower(): k for k, v in {**SYMPTOM_CONCEPTS, **HISTORY_CONCEPTS}.items() if k in symptom_ids | history_ids}
    words = re.findall(r"[a-z0-9']+", text.lower())
    keep = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        cid = it.get("id") or it.get("concept")
        cid = cid if cid in symptom_ids | history_ids else by_label.get(str(cid).lower())
        state = str(it.get("state", "")).lower()
        q = re.findall(r"[a-z0-9']+", str(it.get("quote", "")).lower())
        if cid and state in ("present", "denied") and q and _in_order(q, words):
            keep.append(dict(id=cid, kind="symptom" if cid in symptom_ids else "history", state=state, quote=it["quote"]))
    return keep


def _in_order(quote_words, text_words):
    """Every word of the quote occurs in the clinician's text, in the same order (gaps allowed): copied, not invented."""
    i = 0
    for w in quote_words:
        try:
            i = text_words.index(w, i) + 1
        except ValueError:
            return False
    return True


def _selftest():
    multi = '{"findings": [{"name": "Pleural effusion", "visible": true, "region": "left base", "observations": ["blunted angle"]}]}\n{"findings": [{"name": "Cardiomegaly", "visible": false}]}'
    p = parse_medgemma(multi, ["PLEURAL_EFFUSION", "CARDIOMEGALY"])
    assert p["PLEURAL_EFFUSION"]["visible"] and p["PLEURAL_EFFUSION"]["region"] == "left base" and not p["CARDIOMEGALY"]["visible"], p
    assert parse_box('```json [ {"box_2d": [400, 350, 750, 650]} ] ```') == [0.35, 0.4, 0.65, 0.75]
    assert not box_matches_region([0.4, 0.4, 0.62, 0.75], "right lower lobe")       # midline box for a right-lung finding
    assert box_matches_region([0.1, 0.55, 0.42, 0.9], "right lower lobe") and box_matches_region([0.35, 0.4, 0.65, 0.75], "heart")
    cut = '{"findings": [{"name": "Atelectasis", "visible": true, "region": "right lower lobe", "observations": ["hazy"]}, {"name": "Pleural eff'
    assert parse_medgemma(cut, ["ATELECTASIS", "PLEURAL_EFFUSION"])["ATELECTASIS"]["visible"], "truncated reply must keep complete findings"
    m = np.zeros((100, 100), bool); m[20:60, 30:80] = True
    o = np.array(mask_outline(m))
    assert 0.29 <= o[:, 0].min() and o[:, 0].max() <= 0.8 and 0.19 <= o[:, 1].min() and o[:, 1].max() <= 0.6, o
    assert _NEGATIVE.search("no pleural effusion") and not _NEGATIVE.search("small left pleural effusion")
    t = "bilateral chest tube without visible pneumothorax"
    assert concept_negated(t, t.index("pneumothorax")) and not concept_negated(t, t.index("chest tube"))
    t = "bilateral pneumonia with pleural effusions"
    assert not concept_negated(t, t.index("pleural effusion")) and not concept_negated(t, t.index("pneumonia"))
    g = ground_concepts('[{"id": "orthopnea", "state": "present", "quote": "prop herself up on three pillows"}, {"id": "fever", "state": "present", "quote": "burning up"}]',
                        "She has to prop herself up on three pillows at night", {"orthopnea", "fever"}, set())
    assert [x["id"] for x in g] == ["orthopnea"], g   # 'burning up' is not in the note: invented, dropped
    g = ground_concepts('[{"id": "Shortness of breath", "state": "present", "quote": "winded walking"}]', "gets completely winded walking to the bathroom", {"dyspnea"}, set())
    assert [x["id"] for x in g] == ["dyspnea"], g
    sv = parse_survey('{"findings": [{"name": "left-sided central venous catheter", "region": "left chest"}, {"name": "elevated right hemidiaphragm", "region": "right base"}, {"name": "no pneumothorax"}]}')
    assert [(x["name"], x["maps_to"]) for x in sv] == [("Left-sided central venous catheter", "SUPPORT_DEVICES"), ("Elevated right hemidiaphragm", None)], sv
    sv = parse_survey('```json [ {"name": "Right upper lobe mass", "region": "Lung"}, {"name": "Possible left lower lobe opacity"} ] ```')
    assert [(x["name"], x["maps_to"]) for x in sv] == [("Right upper lobe mass", "LUNG_MASS")], sv
    print("models parsing ok")


def box_matches_region(box, region):
    """Does MedGemma's box sit where its own words say? Patient right = image left on a frontal film.
    A lateral finding (right/left lung, base, apex) must be off the midline and on the named side."""
    if not box or not region:
        return True
    r = region.lower()
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    if re.search(r"\bright\b", r) and not re.search(r"\bleft\b|bilateral|both", r) and cx > 0.45:
        return False
    if re.search(r"\bleft\b", r) and not re.search(r"\bright\b|bilateral|both", r) and cx < 0.55:
        return False
    if re.search(r"\b(?:lower|base|basal|costophrenic)\b", r) and cy < 0.4:
        return False
    if re.search(r"\b(?:upper|apex|apical)\b", r) and cy > 0.6:
        return False
    return True


def parse_box(text):
    """'[{"box_2d": [y0, x0, y1, x1], ...}]' (0-1000) -> [x0, y0, x1, y1] in 0-1, or None."""
    m = re.search(r'"box_2d"\s*:\s*\[([^\]]+)\]', text)
    try:
        y0, x0, y1, x1 = [min(max(float(v) / 1000, 0), 1) for v in m.group(1).split(",")]
    except (AttributeError, ValueError):
        return None
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)] if x1 - x0 > 0.03 and y1 - y0 > 0.03 else None


CONCEPT_STRONG, CONCEPT_WEAK = 25, 300  # best supporting concept rank among 368,294


def concept_rank(concepts, f):
    hits = concepts.get(f, {}).get("for", [])
    return hits[0][1] if hits else 10**9


def is_candidate(levels):
    """Raise a finding only if one reader is at least moderate, or every reader is at least weak (levels: 0..3).
    A finding with a single reliable reader needs that reader to be strong."""
    if len(levels) == 1:
        return levels[0] >= 3
    return max(levels) >= 2 or min(levels) >= 1


# ---------- engine entry points ----------

def load_all(status):
    """Load what is available; each model reports ready/unavailable independently into `status` for the UI."""
    loaded = {}
    status["imaging"] = "loading"
    for key, loader in (("primary", load_clear), ("verifier", load_chexzero)):
        try:
            loaded[key] = loader()
        except Exception as e:
            print(f"[models] {key} unavailable: {e!r}")
    if "primary" in loaded and loaded["primary"].name == "CLEAR":
        try:
            loaded["concepts"] = ConceptBank(loaded["primary"].model)
        except Exception as e:
            print(f"[models] CLEAR concept bank unavailable: {e!r}")
    status["imaging"] = "ready" if "primary" in loaded else "unavailable"
    if "primary" not in loaded and "verifier" in loaded:  # fall back: verifier becomes primary, no independent check
        loaded["primary"] = loaded.pop("verifier")
        status["imaging"] = "ready"
    try:
        loaded["reasoning"] = MedGemma()
        status["reasoning"] = "ready"
    except Exception as e:
        print(f"[models] MedGemma unavailable: {e!r}")
        status["reasoning"] = "unavailable"
    try:
        loaded["segmentation"] = MedSAM()
    except Exception as e:
        print(f"[models] MedSAM unavailable: {e!r}")
    if "primary" not in loaded:
        raise RuntimeError("no imaging model could be loaded")
    return loaded


def analyze(models, img):
    timing, sources = {}, []
    audit = []
    for role in ("primary", "verifier"):
        m = models.get(role)
        if m:
            t = time.time()
            sources.append(dict(role=role, model=m.name, scores=m.scores(img), thresholds=THRESHOLDS[m.name], reliable=RELIABLE[m.name]))
            timing[m.name] = round(time.time() - t, 2)
            audit.append(dict(model=m.name, state="complete", detail="Image scores produced."))
        else:
            audit.append(dict(model=role, state="unavailable", detail="Reader was not loaded."))
    concepts, top_concepts = {}, []
    if models.get("concepts") and models["primary"].name == "CLEAR":
        t = time.time()
        concepts, top_concepts = models["concepts"].explain(models["primary"].last_features)
        timing["CLEAR concepts"] = round(time.time() - t, 2)
        audit.append(dict(model="CLEAR concepts", state="complete", detail="Image matched against the concept bank."))
    else:
        audit.append(dict(model="CLEAR concepts", state="unavailable", detail="Concept retrieval was not available."))
    localizations, descriptions, raw, parsed, cands, rejected = {}, {}, [], {}, [], []
    mg = models.get("reasoning")
    other = []
    if mg:
        level = lambda s, f: sum(s["scores"][f] >= t for t in s["thresholds"][f])
        cands = [f for f in FINDINGS if (lv := [level(s, f) for s in sources if s["reliable"][f]]) and is_candidate(lv)]
        cands = [f for f in cands if SUPPRESSED_BY.get(f) not in cands]
        if concepts:
            # where the concept bank is a reliable reader it is also the specificity check, and it can raise a finding alone
            cr = CONCEPT_READER
            cands = [f for f in cands if not cr.get(f, {}).get("reliable") or concept_rank(concepts, f) <= max(cr[f]["weak"], CONCEPT_WEAK)]
            cands += [f for f, c in cr.items() if c["reliable"] and f not in cands and concept_rank(concepts, f) <= c["strong"]]
        t = time.time()
        other, text = mg.survey(img)  # open-ended: whatever MedGemma sees, catalogue or not
        raw.append(text)
        # MedGemma alone hallucinates on normal films (a "mass" or a "catheter" that is not there): keep a claim only if
        # CLEAR, reading the same phrase zero-shot against the film, agrees
        clear_reader = next((m for m in (models.get("primary"), models.get("verifier")) if m and m.name == "CLEAR"), None)
        if clear_reader and other:
            for o, pr in zip(other, clear_reader.check([o["name"] for o in other], clear_reader.tokenize)):
                o["clear_agreement"] = round(pr, 3)
                o["verified"] = pr >= OPEN_VOCAB_MIN
                o["source"] = "MedGemma 1.5 · CLEAR agrees" if o["verified"] else "MedGemma 1.5 only"
                if not o["verified"]:
                    rejected.append(dict(claim=o["name"], by="MedGemma 1.5",
                                         reason=f"CLEAR, reading the same phrase against the film, disagrees ({pr:.2f} < {OPEN_VOCAB_MIN})"))
        timing["MedGemma survey"] = round(time.time() - t, 2)
        if cands:
            t = time.time()
            parsed, text = mg.describe(img, cands)
            raw.append(text)
            for fid in cands:
                r = parsed.get(fid)
                descriptions[fid] = r["observations"] if r and r["visible"] else ["Visual reasoning model did not identify this finding"]
            # box only what the image models actually support, strongest first
            voters = lambda f: [s for s in sources if s["reliable"][f]]
            # image-model level, or for concept-only findings (emphysema, fibrosis) the concept bank's own level
            def best_level(f):
                if voters(f):
                    return max(level(s, f) for s in voters(f))
                c, r = CONCEPT_READER.get(f, {}), concept_rank(concepts, f)
                return 3 if r <= c.get("strong", 0) else 2 if r <= c.get("moderate", 0) else 0
            strength = {f: best_level(f) + (max(s["scores"][f] for s in voters(f)) if voters(f) else 1 / concept_rank(concepts, f)) for f in cands}
            # never ask for a box around something MedGemma just said it cannot see: the box would be meaningless
            seen = lambda f: (parsed.get(f) or {}).get("visible", True) or any(o.get("maps_to") == f for o in other)
            to_locate = [f for f in sorted(cands, key=strength.get, reverse=True) if best_level(f) >= 2 and seen(f)][:MAX_LOCALIZE]
            for fid in to_locate:
                box, text = mg.locate(img, fid)
                raw.append(text)
                r = parsed.get(fid) or {}
                if box and not box_matches_region(box, r.get("region")):
                    raw.append(f"[box for {fid} discarded: it does not sit in '{r.get('region')}']")
                    rejected.append(dict(claim=f"Outline for {FINDINGS[fid]['name'].lower()}", by="MedGemma 1.5",
                                         reason=f"its box does not sit in the region it described ('{r.get('region')}')"))
                    box = None  # a wrong outline is worse than none; the named region is still reported
                if box:
                    localizations[fid] = dict(bbox=box, region_name=r.get("region") or FINDINGS[fid]["region"], source="MedGemma 1.5")
            timing["MedGemma"] = round(time.time() - t, 2)
    audit.append(dict(model="MedGemma", state="complete" if mg else "unavailable",
                      detail=f"Survey completed; {len(cands)} candidates checked; {len(localizations)} boxes accepted." if mg else "Reasoning model was not loaded."))
    segmentation_state, segmentation_detail = "skipped", "No accepted box to segment."
    if not models.get("segmentation"):
        segmentation_state, segmentation_detail = "unavailable", "Segmentation model was not loaded."
    if models.get("segmentation") and localizations:
        t = time.time()
        try:
            outlines = models["segmentation"].outline(img, {f: l["bbox"] for f, l in localizations.items()})
            segmentation_state, segmentation_detail = "complete", f"{len(outlines)} outlines accepted from {len(localizations)} boxes."
            for fid, contour in outlines.items():
                localizations[fid]["contour"] = contour
                localizations[fid]["source"] += " + MedSAM"
            for fid in set(localizations) - set(outlines):
                rejected.append(dict(claim=f"Segmentation of {FINDINGS[fid]['name'].lower()}", by="MedSAM",
                                     reason="mask was empty or spilled far outside the box; the box is kept"))
        except Exception as e:  # segmentation is a refinement: keep the box, but say so
            segmentation_state, segmentation_detail = "failed", str(e)
            print(f"[models] MedSAM failed, keeping boxes: {e!r}")
            if DEVICE == "cuda":
                torch.cuda.empty_cache()
        timing["MedSAM"] = round(time.time() - t, 2)
    audit.append(dict(model="MedSAM", state=segmentation_state, detail=segmentation_detail))
    regions = {f: r["region"] for f, r in (parsed if mg and cands else {}).items() if r.get("region")}
    return dict(sources=sources, localizations=localizations, descriptions=descriptions, concepts=concepts, top_concepts=top_concepts,
                other_findings=other, regions=regions, rejected=rejected, concept_reader=CONCEPT_READER, masks={}, timing=timing, raw_reasoning=raw, model_audit=audit)
