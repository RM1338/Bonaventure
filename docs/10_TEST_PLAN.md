# Test Plan

## 1. Functional Tests

### Upload
- valid PNG.
- valid JPEG.
- unsupported format.
- corrupted image.

### History
- text PDF.
- multi-page PDF.
- image-based PDF if OCR supported.
- empty document.
- conflicting facts.

### Symptoms
- present symptoms.
- denied symptoms.
- mixed present/denied.
- empty input.

### Report
- generate report with one finding.
- generate report with contradiction.
- generate report with missing history.

## 2. Image Pipeline Tests

- supported finding present.
- supported finding absent.
- multiple findings.
- low-quality image.
- localization returned.
- localization missing.

## 3. History Pipeline Tests

- diagnosis extraction.
- medication extraction.
- prior-imaging extraction.
- date extraction.
- negation.
- source-page preservation.

## 4. Reconciliation Tests

### Strong Agreement
Expected:
SUPPORTED.

### Mixed Support
Expected:
UNCERTAIN.

### Model Disagreement
Expected:
CONFLICTING.

### Missing Context
Expected:
supported image finding with context warning, or reduced evidence state.

### Poor Image
Expected:
INSUFFICIENT_EVIDENCE.

## 5. Negative Evidence Tests

Ensure:
- denied fever is not treated as positive fever.
- “no history of CHF” is not treated as CHF.
- conflicting documents are surfaced.

## 6. UI Tests

- launcher accepts inputs.
- progress states update.
- full review window opens.
- annotation aligns to image.
- evidence panel changes with selected finding.
- report button works.

## 7. Robustness Tests

Create transformed versions:
- blur,
- resize,
- compression,
- slight rotation,
- crop.

Record whether:
- quality warning activates,
- finding changes,
- localization changes.

## 8. Demo Regression Tests

Before evaluation:
- run Case A three times.
- run Case B three times.
- run Case C three times.
- record runtime and output.
- verify report generation.
