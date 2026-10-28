# SHIFTS — the afternoon treaty (Europe/Rome)

One PC, one eye-and-hand (pc-eye), two divisions. The split, as ordered:

| time | who owns the PC | doing what |
|---|---|---|
| 15:00 – 18:00 | **tube-eye posting agent** | work the queue in `plan/schedule.json`: download, hash-check, upload, schedule, receipts |
| 18:00 – 21:00 | **chesseye agent** | the chess project, exactly as before |

The old arrangement gave chess the whole 15:00–21:00/22:00 stretch. It keeps
half, and the other half now ships videos. Both shifts end at a hard wall:
the PC has a human in the evenings.

## Handoff protocol (what each agent does at the boundary)

**Tube-eye, at 17:45:**
1. Stop starting new uploads. A mid-flight upload may finish; nothing new.
2. Push any pending receipts (a delivery without a receipt gets re-planned
   and possibly double-posted — the receipt is the handoff's most important
   artifact).
3. Write `shifts/<date>-<agent>.md` in `storagecode`: what was posted, what
   was skipped and why, what the next agent should know.
4. Say in chat: *"tube-eye shift done, PC free for chesseye."* Close
   YouTube Studio tabs; leave the browser and desktop otherwise as found.

**Chesseye, at ~21:00:** unchanged discipline — its own shift note, its own
ledger rows. It never touches this repo, and the posting agent never touches
its windows, terminals or processes.

## The human's part (2 minutes/day)

1. Before 15:00: start `pc-eye` (`start.bat`), paste the URL+token into the
   posting agent's chat, plus its fine-grained GitHub token for `tube-eye`
   receipts.
2. At the handoff: close the posting session, open the chess session. Same
   pc-eye server can stay up; a fresh tunnel is fine too.
3. Occasionally (weekly is enough): open YouTube Studio → Content and look
   at the Scheduled tab. That list is your veto — cancelling a scheduled
   video there is the designed kill switch, and the lead window guarantees
   you always have ≥ 24 h to use it.

## Empty-queue days

Posting three videos takes well under three hours. When the queue is short,
the posting shift still runs: re-validate intake (`src/intake.py --online`),
re-plan (`src/scheduler.py`), check Studio for videos stuck in Processing,
update receipts, and release the PC early — chess starts early, nothing is
wasted. When the queue is *persistently* short, that is a producer-side
signal, and it belongs on the agency board, not in this repo.

## Why these hours

* 17:00 Rome publishes hit the early-evening slot for European viewers and
  land mid-morning in the Americas — a sane default for an English-language
  channel, and the exact value lives in `config.json` if the analytics ever
  argue otherwise.
* The posting shift sits **before** chess so a failed upload never eats into
  chess time at the tail of the evening, where the human is least available
  to intervene.
