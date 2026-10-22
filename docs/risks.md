# Residual risks

Product-facing risk notes for the HR Policy and Leave Assistant demo. Owners are roles, not individuals.

| Risk | Impact | Likelihood | Owner | Mitigation | Evidence |
| --- | --- | --- | --- | --- | --- |
| Cross-employee data access via prompt | High | Medium | Backend | No employee_id on balance tool; auth from bearer token; API authorization on traces/requests | Offline IDOR tests; live balance smoke as Alya |
| Model invents policy citations | High | Medium | Agent | Citation gate: cited document ids must be retrieved this run; else abstain | Agent reliability tests; evaluation citation validity |
| Leave created without confirmation | High | Low | Actions | prepare saves proposal only; confirm endpoint is the only writer of pending requests | Action/idempotency tests |
| Second prepare silently replaces an open proposal | Medium | Low | Actions | One open proposal; remind until keep/confirm/replace; validate before supersede | `tests/agent/test_proposal_status.py` |
| System claims leave is approved | High | Low | Actions / agent | No approve tool; confirm status fixed to pending_manager_review; forbidden “approved” in eval case | Contracts + evaluation hard gate |
| Prompt injection in user text or policy docs | High | Medium | Agent / retrieval | Treat retrieved text as data; strict tools; refuse cross-user token leakage | Security evaluation cases |
| PII / medical detail in traces | High | Medium | Telemetry | Redact email, phone, token-like values, medical cues before persist | Redaction unit test |
| Redis outage | Medium | Medium | Platform | Cache miss only; Postgres remains source of truth | ResilientCache design; /readyz cache=degraded |
| Embedding / model credential misuse | High | Low | Operator | `.env` gitignored; not copied into image; no build-time secrets | `.dockerignore`, Dockerfile review |
| Evaluation drift vs live model | Medium | Medium | AI Platform | Fixed case set; GO/NO-GO thresholds; re-run before release | `src/run_evaluation.py`, outputs report |
| Overlapping leave accepted | Medium | Medium | Domain | Overlap check against non-cancelled requests | `tests/domain/test_overlap.py` |
| Domain thresholds drift from policy markdown | Medium | Medium | Domain / content | Keep `domain.py` constants aligned with `HR-LEAVE-001` / `HR-LEAVE-002`; prefer typed rules at seed later | Domain unit tests; architecture “search vs domain” note |
| Model skips ticket when sick docs via HR are required | Medium | Medium | Agent | Domain flags `sick_docs_via_hr=required` on prepare; prompt steers ticket + no diagnosis | Domain unit tests; tool description |

## Out of scope for this demo

- Real employee data or production SSO
- Automated leave approval
- Legal advice or medical triage
- Admin policy editor with auto-extracted prepare rules (typed config + human confirm is the intended follow-up)
