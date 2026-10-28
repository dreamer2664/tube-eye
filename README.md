# tube-eye

**The agency's posting division.** Producers make videos; tube-eye gets them
onto YouTube on a schedule — driven by an agent on the PC, through
[`pc-eye`](https://github.com/dreamer2664/pc-eye), the same way the chess
agent rides it every afternoon.

```
producers (competitionvideo28 · youtube-empire · anyone)
   │  MP4 + thumbnail + captions → GitHub Release on storagecode
   │  one manifest JSON          → deliveries/ in this repo
   ▼
intake.py ──validates──▶ plan/intake_report.json
   ▼
scheduler.py ──assigns slots──▶ plan/schedule.json     (1 long-form/day 17:00,
   ▼                                                    2 Shorts/day 13:00,
POSTER.md agent on pc-eye                               ≥24h cancel window)
15:00–18:00 Europe/Rome
   │  browser-download assets → hash-check → YouTube Studio upload
   │  → SCHEDULED at the slot time → verified with eyes on screen
   ▼
receipts/<id>.json here + PUSHES.md/shift note in storagecode
   ▼
18:00 handoff ──▶ chesseye owns the PC until 21:00
```

## Why this exists

`competitionvideo28` proved the crew can produce broadcastable video. The
chess agent proved an agent can hold a PC all afternoon through pc-eye.
tube-eye connects the two: the afternoons get split — **three hours of
YouTube, three hours of chess** ([SHIFTS.md](SHIFTS.md)) — and the videos
stop dying in releases.

## The pieces

| What | Where |
|---|---|
| Cold brief for the posting agent | [POSTER.md](POSTER.md) — read it, then the plan |
| How producers deliver a video | [DELIVERY.md](DELIVERY.md) + [`deliveries/TEMPLATE.json`](deliveries/TEMPLATE.json) |
| The afternoon split & handoff | [SHIFTS.md](SHIFTS.md) |
| Publish cadence, shift times, lead window | [config.json](config.json) |
| Validation | `python3 src/intake.py [--online]` → `plan/intake_report.json` |
| Slot assignment | `python3 src/scheduler.py --print` → `plan/schedule.json` |
| Proof of posting | `receipts/<delivery_id>.json`, one per posted video |

## Safety model, stated plainly

* **Nothing goes public by accident.** Default visibility is YouTube's
  native **Scheduled**, and `min_lead_hours: 24` means every upload sits
  visible-but-unpublished in Studio for a full day. Publishing *now*
  requires `"visibility": "public"` + `"approved_by_human": true` in the
  manifest — a human decision, recorded in the file.
* **The agent's blast radius is the upload flow.** No monetization screens,
  no channel settings, no deletions — enforced as laws in POSTER.md.
* **Hash-verified or it didn't happen.** Intake HEADs every asset URL and
  checks served bytes; the poster re-hashes the downloaded file on the PC
  before uploading. A mismatch is a stop, not a shrug.
* **Evidence over assertion**, per house law: a video is "posted" only when
  a receipt records what the agent *saw* in the Content list.

## The money question, honestly

A channel earns when it joins the YouTube Partner Program (1,000
subscribers + 4,000 public watch-hours in 12 months, or 10M Shorts views).
That threshold is a content problem, not a posting problem — tube-eye makes
the posting side zero-effort so every delivered video actually ships. What
tube-eye will never do: touch AdSense, monetization settings, or anything
that needs the human's legal hands.

## Laws

1. **No secrets in this repo, ever — it is public.** Tokens live in env
   vars or the agent's session, never in a commit.
2. **Additive.** No deletion, no force-push. Corrections are new commits.
3. **Producers never post, the poster never produces.** One job per seat.
4. **The receipt is the record.** No receipt → the scheduler re-plans it.
5. **Red-line repos** (`captchaproject`, `captchaprogram`) are never
   touched, same as everywhere else in the agency.

## Tests

```bash
python3 tests/run_all.py     # 26 tests: schema rules, slot logic, shipped manifests
```

CI (`.github/workflows/ci.yml`) runs the suite plus an offline intake on
every push, so a malformed delivery can never sit silently in the queue.

## Relation to the other repos

* [`pc-eye`](https://github.com/dreamer2664/pc-eye) — the eye and hand. Its
  PC-EYE.md is in force for the posting agent; POSTER.md adds only the
  YouTube specifics.
* [`chesseye`](https://github.com/dreamer2664/chesseye) — the afternoon
  peer. SHIFTS.md is the treaty between the two.
* [`storagecode`](https://github.com/dreamer2664/storagecode) — final videos
  live as its Releases (house rule for large media); the ledger and shift
  notes live there too.
* [`agency`](https://github.com/dreamer2664/agency) — the crew board. This
  division's announcement card is drafted in
  [`agency-job/`](agency-job/) and ready for the Director to file.
* `youtube-empire` (private) — the five-video production line upstream. Its
  JOB-04 output is exactly what lands in `deliveries/`.
