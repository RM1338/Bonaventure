# UI / UX Specification

## 1. Design Direction

The UI should feel:
- clinical,
- precise,
- calm,
- lightweight,
- premium.

Visual inspiration:
- clean medical drama interface language,
- restrained liquid-glass treatment for launcher/chrome,
- solid high-readability evidence areas.

Principle:

`Glass for interface chrome; solid surfaces for evidence.`

## 2. Product Surfaces

### 2.1 Quick Launcher

Purpose:
- fast case creation.

Inputs:
- Add Scan.
- Add Patient History.
- Current Symptoms.
- Analyze.

Visual behavior:
- compact translucent panel,
- subtle blur,
- soft depth,
- minimal text.

### 2.2 Processing State

Show high-level progress:

- Reading scan.
- Parsing patient history.
- Structuring current symptoms.
- Checking evidence.
- Reconciling findings.
- Preparing review.

Avoid showing model jargon in the primary UI.

### 2.3 Full Review Workspace

Primary layout:

- Left: current chest X-ray.
- Right: selected finding and evidence state.
- Lower left: relevant history timeline.
- Lower right: supporting / conflicting evidence.
- Bottom actions: compare, evidence details, generate report.

## 3. Finding Presentation

Example:

```text
Possible Pleural Effusion
Evidence Agreement: HIGH

Imaging        Strong
History        Supports
Symptoms       Supports
Contradiction  None
```

## 4. Image Annotation

Use:
- subtle orange/amber contour,
- arrow,
- label.

Do not obscure the scan.

Allow:
- show/hide overlay,
- inspect raw model localization.

## 5. Color Semantics

- Blue — neutral/clinical information.
- Orange — region of interest / candidate finding.
- Amber — uncertainty.
- Red — critical conflict or severe warning only.
- Green — verified agreement / successful processing.

## 6. Evidence Drilldown

Each finding should expose:

- image-model evidence,
- localization,
- relevant history,
- current symptoms,
- negative evidence,
- contradiction reason,
- technical model metadata.

## 7. Timeline

Display relevant history only.

Example:

```text
2025-01  Congestive heart failure
2025-06  Mild cardiomegaly on prior imaging
2026-09  Furosemide active
Current  Dyspnea + ankle swelling
```

## 8. Accessibility / Readability

- High contrast for medical images.
- No glass overlay on the actual diagnostic image.
- Avoid tiny labels.
- Avoid excessive animation.
- Maintain readable report typography.

## 9. Empty / Failure States

### Missing History
“Patient history not provided. Clinical context support is unavailable.”

### Poor Image
“Image quality is insufficient for reliable analysis.”

### Model Disagreement
“Evidence sources disagree. Human review required.”

### No Supported Finding
“No sufficiently supported finding was identified from the supplied evidence.”
