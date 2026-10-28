# PRODUCERS — instructions for the agents that make the videos

You make videos. Someone else posts them. This file is everything you need to
get your film from "rendered on my machine" to "queued on the channel", and
the rules that keep the posting side from ever having to guess.

Read this once, all the way through. It is short on purpose.

---

## 1 · What your job is, and where it stops

Your job ends at a **file with a verified hash** and a **manifest that passes
intake**. The moment those exist, the video is out of your hands.

| you do | you never do |
|---|---|
| make the film, the thumbnail, the captions | touch YouTube, in any session, for any reason |
| upload them as a Release on `storagecode` | upload media as git blobs |
| compute sha256 + byte size | describe a hash you did not compute |
| write one manifest in `deliveries/` | edit someone else's manifest |
| self-check with `intake.py` before pushing | put a token, cookie or URL in the repo |

One door to the channel: the posting agent, with receipts. If you post it
yourself, the channel gets a video with no receipt, and the scheduler will
plan it again — a double post is a real cost, not a hypothetical one.

---

## 2 · Make the film to spec, or it comes back

These are YouTube's hard limits, enforced by `src/manifest.py`. Failing them
fails CI, so check before you render the last time.

| | long-form (`kind: "video"`) | Short (`kind: "short"`) |
|---|---|---|
| duration | any | **≤ 180 s** — over that and it is not a Short |
| aspect | 16:9, 1920×1080 or better | 9:16, 1080×1920 |
| codec | H.264 / AAC, `yuv420p` | same |
| thumbnail | **required**: PNG or JPG, 1280×720 min, 1920×1080 preferred | optional |
| captions | `.srt`, optional but loved | optional |
| title | ≤ 100 chars, ships verbatim | same |
| description | ≤ 5,000 chars, ships verbatim | same |
| tags | ≤ 500 chars in total (commas count) | same |

`yuv420p` is not fussiness: the wrong pixel format uploads fine and then plays
black in half the browsers. Encode it deliberately:

```bash
ffmpeg -i master.mov -c:v libx264 -pix_fmt yuv420p -crf 18 \
       -c:a aac -b:a 192k -movflags +faststart final.mp4
```

**Disclose what is synthetic.** This channel answers YouTube's altered-content
question honestly, and the answer comes from your manifest
(`synthetic_media_disclosure`). If the film is generated, composited or
reconstructed, that is `true` — and the description should say so in words a
viewer understands. This is not a legal hedge, it is the channel's voice.

---

## 3 · Ship the files as a Release on `storagecode`

Final media never goes into git. It goes into a Release of
`dreamer2664/storagecode`.

Tag it `<producer>-<slug>-rNN` — e.g. `competitionvideo28-eidolon-r1`. Asset
names stay boring and stable; the manifest points at them by URL:

```
https://github.com/dreamer2664/storagecode/releases/download/<tag>/<file>.mp4
https://github.com/dreamer2664/storagecode/releases/download/<tag>/<file>.png
https://github.com/dreamer2664/storagecode/releases/download/<tag>/<file>.srt
```

Then compute what you are about to claim:

```bash
sha256sum final.mp4                                  # 64 lowercase hex chars
stat -c%s final.mp4                                  # bytes   (macOS: stat -f%z)
python3 -c "import json;print(json.load(open('ffprobe.json'))['format']['duration'])"
```

A wrong hash is worse than a missing video: intake catches it online, the
poster re-hashes the file on the PC before uploading, and a mismatch costs an
entire afternoon slot. Compute it, paste it, do not retype it.

---

## 4 · The manifest — one JSON, in `deliveries/`

Copy [`deliveries/TEMPLATE.json`](deliveries/TEMPLATE.json) to
`deliveries/<id>-<slug>.json` and fill it in. Every field, and what happens if
you get it wrong:

| field | rule | why it matters |
|---|---|---|
| `schema_version` | `1` | future migrations |
| `id` | `d-0001` … **next free number**, unique | it names your receipt and your slot; a collision fails CI |
| `title` | ≤ 100 chars | ships verbatim — the poster does not rewrite you |
| `description` | ≤ 5,000 chars | ships verbatim; first line is what shows above the fold |
| `tags` | list of strings, ≤ 500 chars total | joined by commas in Studio |
| `producer` | your agent name | who to ask when something is odd |
| `source_repo` | `dreamer2664/<repo>` | provenance; the channel points at its own work |
| `kind` | `video` or `short` | decides the slot: 17:00 vs 13:00 |
| `visibility` | `scheduled` — almost always | see below |
| `approved_by_human` | `false`, unless a human said publish-now | `public` without it is a hard error |
| `synthetic_media_disclosure` | `true`/`false`, honestly | answers Studio's altered-content question |
| `desired_publish_at` | ISO-8601 or `null` | a wish, not an order — see §5 |
| `video.url` / `.sha256` / `.bytes` / `.duration_s` | https URL, 64 lowercase hex, positive int, positive number | all four are validated; the poster re-hashes on the PC |
| `thumbnail.url` / `.sha256` | required for `kind: "video"` | a long-form with no thumbnail is rejected |
| `captions.url` / `.language` | optional; if present, language required | Studio needs to know the language |
| `notes` | free text | playlist, end screen, chapters — anything the poster should know but must not invent |

**On `visibility`.** `scheduled` is the default and the point of the whole
system: your film sits in Studio, visible to the human, unpublished, for at
least 24 hours. `public` means *publish now* and is only legal together with
`"approved_by_human": true` — and only a human may set that. If you find
yourself typing it, stop and ask.

`unlisted` and `private` exist for previews. They are not slots; ask first.

---

## 5 · When it actually goes out

The scheduler decides, and its rules are in `config.json`:

* **long-form:** 1 per day at **17:00 Europe/Rome**
* **Shorts:** up to 2 per day at **13:00 Europe/Rome**
* **nothing is ever scheduled less than 24 h ahead** — that window is the
  human's veto in Studio

The practical consequence, in one line:

> **To publish at 17:00 on day D, your manifest must be on `main` before
> 15:00 on day D−1.** That is when the posting shift starts, and it works the
> plan as it finds it.

`desired_publish_at` is honoured **only** if it is far enough in the future.
Otherwise the scheduler picks the next free slot and records a `note` in
`plan/schedule.json` saying it did. A wish is not a reservation; do not plan
an announcement around one.

---

## 6 · Check it yourself before you push

```bash
python3 src/intake.py            # schema + house rules   (fast, offline)
python3 src/intake.py --online   # + are the Release URLs real?
```

Both must print `[ok  ]` for **your** file. `--online` also HEADs each asset
and compares the served `Content-Length` with your `video.bytes`, which is how
a mistyped hash or a private Release gets caught at your desk instead of at
17:00 in Studio.

Then, and only then:

```bash
git pull --rebase origin main
git add deliveries/<your-file>.json
git commit -m "delivery: <id> <title> (<producer>)"
git push origin HEAD:main
```

Additive only. No force-push, no rewriting, no deleting someone else's file. A
mistake is fixed with a new commit — or, if the film itself is wrong, with a
**new id**. Never reuse an id: the receipt is keyed to it forever.

---

## 7 · What happens to your delivery next

```
your manifest ──▶ intake.py ──▶ plan/intake_report.json     [ok ] or the errors
                      │
                      ▼
              scheduler.py ──▶ plan/schedule.json           your slot, dated
                      │
                      ▼
        posting agent (15:00–18:00) ──▶ downloads, hash-checks,
                                        uploads as SCHEDULED,
                                        verifies with eyes,
                                        writes receipts/<id>.json
                      │
                      ▼
             18:00 handoff ──▶ the film is live at its slot, or the receipt says why not
```

Where to look:

* **`plan/schedule.json`** — your slot. If you are not in it, intake failed
  (check `plan/intake_report.json`) or you already have a receipt.
* **`receipts/<id>.json`** — the truth. `studio_state`, `scheduled_for`, the
  hash the poster saw, and any `anomalies`.
* **`anomalies`** — if your video was skipped, the reason is here: hash
  mismatch, a copyright warning, an upload that would not finish. Fix the
  film, ship a **new** delivery, and say what changed.

Silence is a bug. If three days pass with no receipt and no anomaly, the shift
report in `storagecode` `shifts/` will say why — read it before assuming the
queue forgot you.

---

## 8 · Things that get a delivery rejected

* `http://` asset URLs, uppercase or truncated sha256, `bytes: 0`.
* A thumbnail missing on a long-form.
* A 200-second "Short".
* Tags or a title that go over the cap — YouTube truncates, we reject.
* `visibility: "public"` without a human's `approved_by_human: true`.
* Reusing an existing `id`.
* A description that does not say the film is synthetic when it is.
* Anything that looks like a secret, a token, or a `trycloudflare.com` URL.
* Editing another producer's manifest to "fix" it. Tell them instead.

## 9 · What "done" looks like

> Delivered: `d-0007` *Title* (short, 142 s) — Release
> `competitionvideo28-eidolon-r3`, video sha256 `61e5…3e63`, thumbnail and en
> captions attached. Intake `[ok ]` offline and online. Slot:
> 2026-11-01 13:00 Rome.

That sentence, in your handoff note, plus a manifest on `main`. Then go make
the next one — that is your seat, and the posting side is not yours.
