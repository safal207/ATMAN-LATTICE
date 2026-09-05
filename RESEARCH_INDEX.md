# ATMAN-LATTICE — research and evidence index

Snapshot: 2026-09-05. Selected-track index, not an exhaustive branch or security audit.

| Track | Exact source | Availability and evidence boundary |
|---|---|---|
| v1.19 reference | [`e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f`](https://github.com/safal207/ATMAN-LATTICE/tree/e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f) | Existing main research core; run instructions in README; not rerun during organization |
| Authority module used by CaPU | [`model/authority.py` at the same SHA](https://github.com/safal207/ATMAN-LATTICE/blob/e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f/model/authority.py) | Component boundary only; not full-runtime integration |
| CaPU composition v1 | [CaPU #103](https://github.com/safal207/CaPU/pull/103), `977864167c65f161e6db87b3d14257a11a67516f` | Historical local record: 55 tests; ordinary equal-guarantee FSM agrees; draft code, not approved by this index |
| CaPU HTTP composition v2 | [CaPU #104](https://github.com/safal207/CaPU/pull/104), `8a2f2a37023a50aeac52cb8c8aed84b2eeceec88` | Historical local record: 28 tests / 14 scenarios / 37 paired snapshots; one trusted host, bypass remains possible |

CaPU is the canonical owner of the composition source and evidence. Consult its [research index](https://github.com/safal207/CaPU/blob/main/RESEARCH_INDEX.md) and the immutable source PR heads above. Do not fork the same evidence into four divergent copies. If a new documentation index is not yet on main, the pinned PR sources remain the authority for code identity.

## Preserved history

[README.previous.md](README.previous.md) retains the complete protocol history through v1.19. No historical layer has been relabeled as invalid merely because it is older. New recovery decisions preserve prior evidence rather than rewriting it.

## Next useful boundary

Separate fast action authorization from slower calibration/revision work; validate a deployment-specific trust boundary before claiming production safety. Neither identity, a graph edge nor a historical PASS proves external causality.
