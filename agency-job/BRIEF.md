# BRIEF — t-20261028-tube-eye  (draft card — Director files it into agency/jobs/)

<!-- EPOCH: 2026-10-20.1 · briefs reference law, they never restate it -->
**Owner seat:** manager `director` · **Lane:** `dreamer2664/tube-eye` ·
**Size:** S · **Board card:** `t-20261028-tube-eye` (proposed)

## Deliverable (the contract — one package a stranger can verify)

The posting division `dreamer2664/tube-eye` exists and is wired:

- `deliveries/` intake with validation (`src/intake.py`, offline + online),
- deterministic slot assignment (`src/scheduler.py` → `plan/schedule.json`,
  1 long-form/day 17:00 Rome, 2 Shorts/day 13:00, ≥ 24 h lead window),
- `POSTER.md`: the posting agent's cold brief, riding `pc-eye` under the
  same laws as `PC-EYE.md`, receipts in `receipts/`,
- `SHIFTS.md`: the afternoon split 15:00–18:00 tube-eye / 18:00–21:00
  chesseye, with a handoff protocol,
- first delivery seeded: `d-0001` (eidolon's *The Signal at 37.5*, assets
  hash-verified against the `storagecode` release),
- CI green: 26 tests + offline intake on every push.

## Definition of done

- [x] every line above exists at a pushed SHA (tube-eye `main`)
- [x] `python3 tests/run_all.py` green; `src/intake.py --online` green
- [ ] **first live shift**: d-0001 uploaded as Scheduled by the posting
      agent, receipt pushed, Content-list state seen and recorded
- [ ] Director ratifies the SHIFTS.md treaty with the chesseye seat

## Scope boundaries

- in: intake, scheduling, posting brief, receipts, shift treaty
- out: video production (producers' lanes), monetization/AdSense (human
  only), anything touching the red-line repos

## Hard constraints

- default visibility **scheduled**, publish-now only via
  `approved_by_human: true` in a manifest
- no secrets in the repo (public); tokens are per-agent fine-grained,
  `tube-eye` contents r/w only
- additive history; receipts immutable
