# PDF Report Specification

## 1. Purpose

The report is an evidence summary for clinician review.

It is not a definitive diagnosis report.

## 2. Title

**Bonaventure — Clinical Evidence Review**

## 3. Required Sections

### A. Case Summary
- Case ID.
- Analysis timestamp.
- Input summary.

### B. Current Presentation
- Original symptom text.
- Structured symptoms.

### C. Relevant Patient History
- Time-ordered relevant facts.
- Source references.

### D. Imaging Review
- Current chest X-ray.
- Annotated region(s).
- Candidate findings.

### E. Finding Evidence Table

For each finding:
- finding name,
- evidence state,
- image support,
- history support,
- symptom support,
- negative evidence,
- contradiction state,
- evidence strength.

### F. Clinical Evidence Diagram
A simple thoracic anatomy diagram may be used if it accurately corresponds to the finding.

Do not use a full-body illustration merely for decoration.

### G. Limitations
- model limitations,
- missing data,
- image-quality issues,
- unresolved contradictions.

### H. Review Statement
Suggested wording:

> This report is generated as clinical decision support from the supplied imaging and contextual evidence. It is not a definitive diagnosis and requires review by a qualified clinician.

## 4. Example Finding Section

```text
Possible Right Pleural Effusion

Evidence State: SUPPORTED
Evidence Strength: HIGH

Image:
Localized abnormality near the right costophrenic angle.

Supporting Context:
- Dyspnea.
- Known congestive heart failure.
- Peripheral edema.

Contradictory Evidence:
None identified in supplied context.

Review:
Clinical correlation and radiologist review are recommended.
```

## 5. Provenance Appendix

For technical evaluation, include:
- source document,
- page,
- extracted fact,
- model used,
- localization type,
- model version.

## 6. Report Design

Keep:
- white / light background,
- high contrast,
- minimal decorative elements,
- restrained medical accent colors,
- clear hierarchy.

The report should prioritize evidence readability over stylistic spectacle.
