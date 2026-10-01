# Written Research Dataset Implementation Plan

> For agentic workers: use superpowers:executing-plans inline in the existing shared checkout.

**Goal:** Complete the joint synthetic P1-09b engineering pipeline.
**Architecture:** File-only assignment, observer/source reconciliation, blinded packet and separate
rating/report utilities; reuse research_export and research_ledger, never write product state.
**Tech Stack:** Python, reviewed file bank, existing finite deterministic scorer, pytest.
**Spec:** ../specs/2026-10-01-written-research-dataset-design.md

## Constraints and review focus

Human use closed; complete-history/support flags never inferred; exact source first responses stay
immutable; heldouts separate from live practice; no response keys in blinded packets; withdrawal
must invalidate all linked outputs. Review consent/owner mismatch, late contacts, duplicate probes,
missing versus empty responses, tampered source pins and accidental identity disclosure.

## Tasks

- [x] Add RED tests for assignment balance/pins and input reconciliation; implement frozen helpers
  in backend/app/research_dataset.py with tests/test_research_dataset.py.
- [x] Add RED joined-history, probe isolation, blind-ID reuse and rating tests; implement build_dataset
  and analysis/ratings with the existing ledger/scorer and bounded private output helpers.
- [x] Reconcile six P0 truth histories, run focused tests, independently review and fix findings.
- [x] Add reproducible CLI/synthetic private dataset check, verify no DB/projection mutation.
- [x] Run full backend/PostgreSQL/real-browser checks, Ruff and reviewed diff; update product-state
  and protocol with engineering evidence and precise remaining human gates.

No staging/commits: preserve all existing user/P0/P1/P2 changes.

## Execution record

Ruling: retain inline work in the existing dirty shared checkout and record verification here,
without staging/commits — the user's preservation instruction is binding; cost if wrong is a later
integration review of the combined diff.

Ruling: the synthetic utility freezes the complete cohort mapping before any included practice;
seed/order are prespecified before enrollment — no late enrollment or slot reuse is inferred;
cost if wrong is a protocol revision before human collection, which remains closed.

Assignment/join, ratings/private files and CLI/source serialization used failing tests followed by
implementation and focused GREEN. Source workload retains the actual local allocation window;
the actual serialized DB export integration caught and fixed a window-field contract mismatch.
The source exporter uses JSON-ready snapshots, including nested workload fields.

Final review: Astra backend reviewer found two Important issues: linked contacts could hide prior
exposure/help, and unknown-start probes could omit a known heldout leakage incident. Four failing
regressions reproduced these; linked display/support validation, exact initial-contact exemption
and first-response cutoff fixed them. Focused suite: 62 passed. Full backend with PostgreSQL and
actual HTTP/Chromium: 929 passed. Ruff and diff checks passed. No deferred minor findings.

Human-use consent/custodian and actual blinded rubric trial remain open. P1-09b is not complete.
