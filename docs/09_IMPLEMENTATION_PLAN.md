# Implementation Plan

## 1. Team Structure

Four members.

Two primary builders handle the critical path.
Two supporting members own isolated subsystems that still produce substantial deliverables.

## 2. Ownership

### Member 1 — System / AI Integration Lead

Own:
- architecture,
- backend,
- case orchestrator,
- evidence reconciliation,
- API integration,
- final integration,
- technical decision log.

Critical responsibility:
**Evidence reconciliation engine.**

### Member 2 — Medical Vision + Review Screen

Own:
- image-model setup,
- preprocessing,
- inference,
- finding normalization,
- localization,
- optional verifier,
- image annotation integration.

### Member 3 — Patient History + Symptoms Pipeline

Own:
- PDF parsing,
- OCR fallback if required,
- clinical entity extraction,
- date normalization,
- negation handling,
- patient timeline,
- symptom parsing,
- source provenance,
- demo history documents.

### Member 4 — Product Surface + Reporting + Evaluation

Own:
- quick-launcher UI,
- upload flow,
- processing states,
- report generator,
- PDF template,
- evaluation harness,
- demo-case packaging,
- README support.

## 3. Parallel Dependency Plan

```text
Design freeze
   │
   ├── Member 2: image pipeline
   ├── Member 3: history/symptom pipeline
   ├── Member 4: UI/report with mock APIs
   └── Member 1: backend/reconciliation
              │
              ↓
          Integration
```

## 4. First 90 Minutes

All members together:
- freeze MVP,
- freeze finding set,
- choose model candidates,
- agree JSON contracts,
- agree repository layout,
- define three demo cases,
- create branches/tasks.

No feature creep after this without explicit team decision.

## 5. 18-Hour Build Plan

### Hour 0–1.5
Design freeze.

### Hour 1.5–5
Independent foundations.

Milestone:
Every subsystem returns a valid mock/real response.

### Hour 5–8
First end-to-end path.

Milestone:
One patient case goes from input to review screen.

### Hour 8–11
Build differentiator:
- positive evidence,
- negative evidence,
- contradiction,
- uncertainty,
- agreement state.

### Hour 11–13
Improve localization and review workspace.

### Hour 13–15
Report generation and robustness.

### Hour 15–17
Demo hardening:
- three cases,
- repeated runs,
- deterministic settings,
- failure testing.

### Hour 17–18
Submission:
- public repo,
- README,
- setup,
- sample input/output,
- declared resources,
- scope note.

## 6. Branch Strategy

Suggested:
- `main`
- `dev`
- `feature/image-pipeline`
- `feature/history-pipeline`
- `feature/ui`
- `feature/reconciliation`
- `feature/report`

## 7. Definition of Done

A task is done only when:
- code is committed,
- input/output contract matches spec,
- at least one test exists,
- sample output is stored,
- failure state is handled.
