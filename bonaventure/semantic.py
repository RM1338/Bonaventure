"""Meaning-based fallback for phrases the clinical vocabulary does not recognise: embed the phrase (MiniLM, CPU) and pick the
closest concept by cosine similarity. Only a clear, well-separated match is accepted; anything else is reported as not used."""
import os
import re
from pathlib import Path

import numpy as np

from .knowledge import HISTORY_CONCEPTS, SYMPTOM_CONCEPTS

MODEL_DIR = Path(os.environ.get("BV_MINILM", Path.home() / "bonaventure/models/minilm"))
MIN_SIMILARITY = 0.40   # cosine; calibrated on paraphrase tests (below: "not understood")
MIN_MARGIN = 0.08       # best concept must clearly beat the runner-up, else ambiguous -> not used


def _readable(pattern):
    """Turn a lexicon regex into plain words for the concept description ('short of breath', 'can't lie flat')."""
    p = re.sub(r"\(\?:([^)|]*)\|[^)]*\)", r"\1", pattern)          # (?:a|b) -> a
    p = re.sub(r"\\w\*|\\w\+|\\b|\\s\*|\[[^\]]*\]|[?*+(){}^$\\|]|\.\{[^}]*\}", " ", p)
    return " ".join(p.split())


class ConceptMatcher:
    def __init__(self):
        from transformers import AutoModel, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(MODEL_DIR)
        self.model = AutoModel.from_pretrained(MODEL_DIR).eval()
        self.ids, texts = [], []
        for cid, (label, pats) in SYMPTOM_CONCEPTS.items():
            self.ids.append(("symptom", cid))
            texts.append(f"{label}: " + ", ".join(_readable(p) for p in pats[:4]))
        for cid, (label, _cat, pats) in HISTORY_CONCEPTS.items():
            self.ids.append(("history", cid))
            texts.append(f"{label}: " + ", ".join(_readable(p) for p in pats[:4]))
        self.vecs = self._embed(texts)

    def _embed(self, texts):
        import torch
        with torch.inference_mode():
            b = self.tok(texts, padding=True, truncation=True, max_length=64, return_tensors="pt")
            out = self.model(**b).last_hidden_state
            mask = b["attention_mask"].unsqueeze(-1).float()
            v = (out * mask).sum(1) / mask.sum(1)
            return torch.nn.functional.normalize(v, dim=-1).numpy()

    def match(self, phrase):
        """-> (kind, concept_id, similarity) or None when nothing is clearly meant."""
        sims = self.vecs @ self._embed([phrase])[0]
        order = np.argsort(-sims)
        best, second = sims[order[0]], sims[order[1]]
        if best < MIN_SIMILARITY or best - second < MIN_MARGIN:
            return None
        kind, cid = self.ids[order[0]]
        return kind, cid, round(float(best), 3)


_matcher = None


def matcher():
    global _matcher
    if _matcher is None and MODEL_DIR.exists():
        _matcher = ConceptMatcher()
    return _matcher


if __name__ == "__main__":
    m = matcher()
    for p in ["I can't catch my breath", "my chest feels tight", "sweating buckets at night", "throwing up blood", "coughing up blood",
              "my ankles are puffy", "she's been off her food", "feels like an elephant on my chest", "the weather is nice"]:
        print(f"{p!r:45} -> {m.match(p)}")
