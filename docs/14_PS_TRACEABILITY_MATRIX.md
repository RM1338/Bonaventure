# HackNex PS05 Traceability Matrix

## 1. Requirement Mapping

| PS05 Requirement | Bonaventure Feature | Verification |
|---|---|---|
| Read medical images | Chest X-ray ingestion | Demo upload |
| Combine image with patient notes/test results | History pipeline + reconciliation | Case review |
| Give an assessment | Finding evidence bundle | Review screen |
| Point to exact region | Bounding box / mask / annotation | Image overlay |
| Explain what was found | Evidence panel | Finding drilldown |
| Include confidence | Evidence-strength state | Review screen |
| Unsupported findings fail | Evidence gate | Test cases |
| Helper, not replacement | Clinician-support language | UI/report copy |
| Spot/classify abnormalities | Image model | Evaluation |
| Use both image and patient context | Reconciliation engine | Demo case |
| Segment/outline problem areas | Optional segmentation / contour | Stretch demo |
| Realistic confidence | Evidence score / calibrated output | Evaluation |
| Handle poor-quality images | Quality gate | Robustness test |

## 2. “What to Build First” Alignment

PS recommends:
1. Public medical datasets.
2. One type of abnormality on single images with heatmap.
3. Advanced segmentation and image + patient notes.

Bonaventure follows the same progression:

### Phase 1
One validated finding, one X-ray, localization.

### Phase 2
Multiple findings.

### Phase 3
Patient-history and symptom reconciliation.

### Phase 4
Segmentation / richer localization.

## 3. Submission Requirements Mapping

| General Submission Requirement | Bonaventure Artifact |
|---|---|
| Working system | Desktop application + backend |
| Source code | Public repository |
| Data pipeline | Architecture + AI pipeline docs |
| Core model / reasoning | Image models + reconciliation engine |
| Evidence & explanation | Evidence bundles + source provenance |
| Sample input/output | Demo cases |
| Scope note | PRD MVP/stretch sections |
| Live demonstration | Demo plan |
