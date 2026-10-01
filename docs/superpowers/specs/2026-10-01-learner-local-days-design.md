# Learner local days — P2-03 design

Reviewed by Astra under the owner's autonomous development instruction, 2026-10-01.
Purpose: align review/quiz calendar boundaries and written issuance budgets with a selected IANA
zone, retaining UTC instants and consumed allocations. Authentication remains deferred.

## Profile and transition

Add timezone (requested, default UTC), previous_timezone (default UTC), timezone_change_at and
timezone_window_start (nullable UTC instants). Validate IANA keys before persistence. A repeated
request for the same requested zone is idempotent. A changed request locks the profile, reads the
DB clock after locking, and freezes the current allocation start. Its activation is the first
existing day boundary in the requested zone at or after the current allocation end. Pending
replacement preserves the original effective zone/start and never shortens that end. At the exact
activation instant the new zone is effective. No event, issued quiz plan or historical snapshot
is rewritten. Four fields cannot reconstruct historical travel; issued snapshots retain windows.

Calendar days/weeks use the effective zone; transition allocations use the frozen start/extended
end. First existing local-day instant handles skipped/ambiguous midnight and skipped dates;
choose the earlier UTC instant at a repeated midnight. UTC half-open windows may be 23/25 hours.
The transition can be longer than a day; repeated changes can extend it. UI shows requested and
effective zones, UTC reset instant and remaining counts without calling transition counts today.
Old profiles have an explicitly disclosed UTC fallback. Never detect or change zone automatically.

## Product integration

- Profile GET/create and PATCH retain existing fields, add requested/effective zone and allocation
  window. Old clients can omit timezone. Profile lock precedes run lock everywhere.
- All review list/status/grade unscheduled fallback uses the same local day start. Existing due
  instants and review intervals remain absolute UTC durations.
- Daily quiz prioritizes local-day touches; weekly includes local Monday onward. Frozen plans stay
  readable; quiz key logic is unchanged.
- Written issuance counts use window, with named written-local-budget-v2, effective zone and exact
  UTC start/end/transition pinned in new snapshots. Existing v1/v2 selector runs remain readable;
  selector ranking is unchanged. Existing legacy word setting remains session batch size.
- Counts are measured issuance/review items, not forecast minutes. No public research endpoint,
  human collection, new planner or hard mastery rule.

## Verification

Short/long DST day, midnight gap/fold, skipped date, exact activation, date-line travel, repeated
and replaced requests, UTC migration and malformed zone. Verify quota preservation, local midnight
rollover and simultaneous profile PATCH/next/repair with PostgreSQL; verify all review paths agree
and quiz week/day boundaries. Frontend checks form disclosure, API payload and workload reset.
Full backend, frontend unit/type/build/browser checks and reviewed diff precede completion.
Observed participant workload/burden remains unmeasured until the feasibility pilot.
