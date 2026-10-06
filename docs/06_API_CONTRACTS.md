# API Contracts

## 1. Goal

All major modules should be independently buildable.

Frontend must be able to work with mocks before real model integration.

## 2. Create Case

`POST /cases`

Response:

```json
{
  "case_id": "CASE_001",
  "state": "CREATED"
}
```

## 3. Upload Scan

`POST /cases/{case_id}/scan`

Response:

```json
{
  "file_id": "scan_001",
  "status": "uploaded"
}
```

## 4. Upload History

`POST /cases/{case_id}/history`

Response:

```json
{
  "files": [
    {
      "file_id": "hist_001",
      "name": "history.pdf",
      "status": "uploaded"
    }
  ]
}
```

## 5. Add Symptoms

`POST /cases/{case_id}/symptoms`

Request:

```json
{
  "text": "Shortness of breath for three days, ankle swelling, no fever."
}
```

Response:

```json
{
  "raw": "Shortness of breath for three days, ankle swelling, no fever.",
  "normalized": [
    {"concept": "dyspnea", "state": "present", "duration": "3 days"},
    {"concept": "peripheral_edema", "state": "present"},
    {"concept": "fever", "state": "denied"}
  ]
}
```

## 6. Start Analysis

`POST /cases/{case_id}/analyze`

Response:

```json
{
  "case_id": "CASE_001",
  "state": "PROCESSING"
}
```

## 7. Analysis Status

`GET /cases/{case_id}/status`

Response:

```json
{
  "state": "RECONCILING",
  "steps": {
    "image_quality": "complete",
    "image_analysis": "complete",
    "history_parse": "complete",
    "symptom_parse": "complete",
    "reconciliation": "running"
  }
}
```

## 8. Get Case Result

`GET /cases/{case_id}`

Response:

```json
{
  "case_id": "CASE_001",
  "state": "REVIEW_READY",
  "quality": {
    "state": "acceptable",
    "warnings": []
  },
  "timeline": [],
  "symptoms": [],
  "findings": []
}
```

## 9. Finding Object

```json
{
  "id": "finding_01",
  "canonical_name": "PLEURAL_EFFUSION",
  "display_name": "Possible pleural effusion",
  "status": "SUPPORTED",
  "evidence_strength": "high",
  "localization": {
    "type": "bbox",
    "coordinates": [0.61, 0.68, 0.84, 0.91],
    "region_name": "right costophrenic angle"
  },
  "image_evidence": [],
  "history_evidence": [],
  "symptom_evidence": [],
  "negative_evidence": [],
  "contradictions": [],
  "clinician_text": "Consider a possible right pleural effusion. Imaging and supplied context are concordant."
}
```

## 10. Generate Report

`POST /cases/{case_id}/report`

Response:

```json
{
  "status": "generated",
  "report_path": "reports/CASE_001.pdf"
}
```

## 11. Error Contract

```json
{
  "error": {
    "code": "INVALID_SCAN",
    "message": "The uploaded image could not be analyzed.",
    "details": []
  }
}
```

Allowed major error codes:
- INVALID_SCAN
- UNSUPPORTED_FILE
- HISTORY_PARSE_FAILED
- IMAGE_MODEL_FAILED
- REPORT_GENERATION_FAILED
- INSUFFICIENT_EVIDENCE
