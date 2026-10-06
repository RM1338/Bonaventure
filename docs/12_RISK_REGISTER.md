# Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---:|---|
| Primary model fails on demo image | Very high | Medium | Use validated demo cases; independent verifier; cached fallback for non-live explanation only |
| Localization is visually wrong | Very high | Medium | Validate localization separately; avoid claiming segmentation if only attribution |
| Model confidence is misleading | High | High | Use evidence-strength categories; label raw model scores clearly |
| History parser hallucinates facts | High | Medium | Preserve source provenance; show extracted text; restrict LLM to structured extraction |
| Negation is parsed incorrectly | High | Medium | Add explicit negation tests |
| Patient-history documents conflict | Medium | Medium | Surface contradiction instead of resolving silently |
| Poor image quality creates false result | High | Medium | Quality gate and INSUFFICIENT_EVIDENCE state |
| UI blocks model integration | High | Medium | Freeze API contracts and use mocks |
| Large model download/inference fails | High | Medium | Validate model availability early; keep fallback model |
| GPU memory insufficient | High | Medium | Benchmark at start; choose smaller model |
| Network dependency fails | High | Medium | Prefer local inference for demo-critical path |
| Report generation breaks late | Medium | Low | Build report template early |
| Team members block each other | High | Medium | Parallel module ownership |
| Feature creep | High | High | Freeze MVP after design session |
| Judge interprets output as diagnosis | High | Medium | Decision-support language everywhere |
| Real patient privacy issue | Very high | Low | Use public/de-identified/synthetic data only |
| Unsupported claim appears in report | Very high | Medium | Report only from structured evidence bundle |
