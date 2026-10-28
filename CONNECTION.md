# CONNECTION — how tube-eye is wired to pc-eye, and how that link is proven

This file exists because the link between this repo and the PC is the one part
that cannot be tested from CI: it depends on a tunnel that changes its name
every time the human double-clicks `start.bat`. Everything else here is
deterministic; that is not.

**One command decides whether a shift may start:**

```bash
export PC_EYE_URL=https://<something>.trycloudflare.com     # from start.bat
export PC_EYE_TOKEN=<32 hex chars>                          # from start.bat
python3 src/preflight.py --act
```

Exit `0` or `2` → post. Exit `1` → do not touch the PC; read the failing line
and follow it. `--json` for a machine-readable report, `--queue-only` to check
the plan with no network at all.

---

## The two halves

```
tube-eye (this repo)                     pc-eye (the PC)
  plan/schedule.json   ── what to post ──▶   /state   screen, cursor, coord_space, dry_run
  deliveries/*.json    ── the manifest ──▶   /selftest what the machine can actually do
  src/preflight.py     ── proves it ─────▶   /shot    the eyes (+ sizes as headers, + changed=)
  receipts/*.json      ◀─ proof it did ───   /act     the hand (one action per call)
```

The posting agent reads [`POSTER.md`](POSTER.md) for the *procedure* and
[`PC-EYE.md`](https://github.com/dreamer2664/pc-eye/blob/main/PC-EYE.md) for
the *laws and traps of the PC*. This file is the contract between the two
repos: which routes tube-eye depends on, what each failure means, and what
"connected" is allowed to mean.

## What preflight checks, and why each one exists

| Check | Green means | If it fails |
|---|---|---|
| `url` / `url-tls` | an `https://` tunnel host (plain http only tolerated on loopback) | the token would cross the internet in clear — fix the URL |
| `token` | non-empty, length printed, **value never printed or logged** | ask the human to re-read `start.bat`; never guess |
| `state` | `/state` answers 200 within a few seconds | `401` → wrong token · `unreachable` → **the tunnel URL changes every run**, ask for the fresh one · nothing → the PC is asleep or the window was closed |
| `not-dry-run` | `dry_run: false` | the human started the server in demo mode: every `ok` is a recording, nothing reaches the machine |
| `coord-space` | `coord_space.consistent: true` | eyes and hand are in different pixel spaces (DPI scaling). This really happened on 2026-10-16 — a click aimed at (1800,933) landed at (1535,863) and returned `ok`. **Do not scale by hand. Stop.** |
| `capture` | `capture_ok: true` | the agent would be blind |
| `selftest` / `selftest-no-test-mode` | every machine check green, no `TEST-MODE` row | report the red lines verbatim in chat |
| `shot` + `shot-headers` | a real image, plus `X-Screen-Full` and `X-Screen-Sent` | without both sizes you cannot aim: `x_real = x_seen * full_w / sent_w` |
| `shot-changed` | `GET /shot?changed=<hash>` answers **304** | this is how a 600 MB download is *waited for*; if it returns frames instead, a long wait becomes hundreds of wasted captures (and a 429) |
| `act-move` | `exact: true` and `landed` where asked | `exact: false` means the click did not go where you aimed — stop, re-read `/state` |
| `latency` (warn) | `/state` under 3 s | a slow tunnel makes every click feel frozen; prefer `changed=` waits |
| `screen-size` (warn) | at least 1024×700 | Studio's layout assumes a desktop window |
| `next-slot` / `queue` | a future slot with no receipt | nothing to post — run `intake.py` + `scheduler.py`, or say so and release the PC |

## What the link guarantees — and what it does not

**It does.** That the agent can see the screen it is clicking, that its clicks
land where it aimed, that it is not driving a demo server, and that the queue
it is about to work through is real and current.

**It does not.** That YouTube is logged in, that Studio has the layout it had
last week, that the file will download at any particular speed, or that an
upload will be accepted. Those are facts about the session and the platform;
they are discovered with eyes on screen, exactly as `POSTER.md` describes, and
recorded in the receipt.

The link is a **precondition**, never evidence of posting. The only evidence of
posting is a receipt describing what the agent saw in the Content list.

## Token handling, stated once

* The token is the only lock on a door facing the open internet, and it travels
  in a URL. It is 32 hex characters.
* It goes in `PC_EYE_TOKEN` (or `--token`). It is never committed, never pasted
  into the repo, never put in a manifest, never sent to the wire.
* `preflight.py` prints its *length*, not its value — there is a test that
  fails if the value ever appears in a report (`tests/test_preflight.py`).

## When the PC changes underneath you

The tunnel is not stable, by design: `start.bat` prints a new URL every run.
So a link that worked an hour ago proves nothing now. That is why preflight is
cheap enough to run *before every delivery*, not once per shift — the queue
half alone (`--queue-only`) is free and needs no network.

| Symptom | Meaning | Move |
|---|---|---|
| `unreachable: Name or service not known` | the tunnel is gone (PC asleep, window closed, or a new URL) | ask the human for the two fresh lines. Do not retry the old host. |
| `401` | token rotated or mistyped | same: fresh lines, never a guess |
| `409` on `/act` | the hand cannot reach that coordinate, or the spaces disagree | stop the shift, report |
| `429` | too many requests | use `/shot?changed=<hash>` while waiting |
| `503` | the machine could not capture | tell the human; it is not fixable from a chat |

## Verifying this contract without a PC

`tests/test_preflight.py` runs the whole handshake against a protocol-faithful
stub (`tests/fake_pc_eye.py`) covering the states that have actually broken
shifts: dead tunnel, wrong token, demo mode, coordinate mismatch, missing shot
headers, a `changed=` that does not return 304. That is what CI proves. What CI
cannot prove — and the human's `start.bat` does, once per afternoon — is that
the *real* machine answers the same way.
