# Demo and Acceptance Plan

## 1. Demo Objective

Demonstrate that Bonaventure can:

- read chest X-ray evidence,
- parse patient history,
- understand current symptoms,
- localize a candidate finding,
- reconcile multimodal evidence,
- surface uncertainty,
- generate a traceable report.

## 2. Three Required Demo Cases

### Case A — High Agreement

Inputs:
- X-ray with supported finding.
- History supporting the finding.
- Symptoms supporting the finding.

Expected:
- SUPPORTED.
- Visible localization.
- High evidence strength.

### Case B — Contradiction

Inputs:
- image model suggests finding,
- independent verifier or clinical context disagrees.

Expected:
- CONFLICTING.
- explicit contradiction panel.
- human review required.

### Case C — Poor / Ambiguous Evidence

Inputs:
- degraded image or weak image signal,
- limited context.

Expected:
- UNCERTAIN or INSUFFICIENT_EVIDENCE.
- no forced definitive output.

## 3. Demo Script

1. Open compact launcher.
2. Add chest X-ray.
3. Add patient history.
4. Enter current symptoms.
5. Start analysis.
6. Show processing states.
7. Open full review.
8. Select candidate finding.
9. Show localized region.
10. Show relevant patient timeline.
11. Show supporting symptom/history evidence.
12. Show negative evidence.
13. Show evidence state.
14. Open technical drilldown.
15. Generate PDF.
16. Show contradiction demo.

## 4. Acceptance Checklist

- [ ] Working solution.
- [ ] Public Git repository.
- [ ] Clear README.
- [ ] Install instructions.
- [ ] Run instructions.
- [ ] Data pipeline shown.
- [ ] Core reasoning mechanism explained.
- [ ] Evidence provided.
- [ ] Sample input/output included.
- [ ] MVP vs stretch goals clearly separated.
- [ ] Live demo ready.
- [ ] All external models/APIs/datasets declared.
- [ ] At least one image-localized finding demonstrated.
- [ ] Image + patient context used together.
- [ ] Confidence/evidence strength shown.
- [ ] Poor-quality or uncertainty case demonstrated.
- [ ] Report generated successfully.

## 5. Demo Rule

Never choose a demo case that has not been tested end-to-end before evaluation.
