# DELIVERY — how a producer hands a video to the posting division

You made a video. Here is how it gets onto the channel without you touching
YouTube. Two artifacts: **the files** (GitHub Release) and **the manifest**
(one JSON in `deliveries/`). The poster agent does the rest.

## 1 · The files → a Release on `storagecode`

House rule for large media: final videos are **Release assets of
`dreamer2664/storagecode`**, never git blobs. Tag it
`<venue>-<producer>-rNN` (e.g. `competitionvideo28-eidolon-r1`) and upload:

| asset | required | notes |
|---|---|---|
| the MP4 | yes | H.264/AAC, yuv420p; Shorts ≤ 180 s, 9:16 |
| thumbnail PNG/JPG | yes for long-form | 1280×720 minimum, 1920×1080 preferred |
| captions `.srt` | optional but loved | word-accurate beats auto-generated |

Compute and write down `sha256` and byte size for each — the intake checks
them against what the server actually serves, and the poster re-hashes the
file on the PC before uploading. A wrong hash wastes an afternoon slot.

## 2 · The manifest → `deliveries/<id>-<slug>.json`

Copy [`deliveries/TEMPLATE.json`](deliveries/TEMPLATE.json). The fields that
matter:

* **`id`** — `d-0001`, `d-0002`, … unique, next free number (check the
  folder; collisions fail CI).
* **`title`** — ≤ 100 chars. It ships verbatim; the poster does not edit it.
* **`description`** — ≤ 5,000 chars, ships verbatim. Say what is synthetic
  or reconstructed; this channel discloses.
* **`kind`** — `video` or `short` (shorts: ≤ 180 s).
* **`visibility`** — almost always `scheduled`. `public` (publish now) is
  only valid together with `"approved_by_human": true`, which only the
  human may set. `unlisted`/`private` exist for previews.
* **`desired_publish_at`** — optional ISO-8601. Honoured when it respects
  the 24 h lead window; otherwise the scheduler picks the next free slot
  and says so in the plan.
* **`synthetic_media_disclosure`** — the honest answer to YouTube's
  altered-content question for *this* film.

## 3 · Check it before you push

```bash
python3 src/intake.py            # offline: schema + house rules
python3 src/intake.py --online   # also: are your release URLs real?
```

Both must print `[ok ]` for your file. Then commit the manifest to `main`
(additive, no force-push) and announce on the wire, as usual.

## 4 · What happens next

The scheduler gives your delivery a slot (1 long-form/day at 17:00 Rome,
2 Shorts/day at 13:00, never inside the 24 h lead window). The posting
agent downloads, hash-checks, uploads as **Scheduled**, and writes
`receipts/<id>.json`. Watch your video appear in `plan/schedule.json` →
then in `receipts/`. If it lands in `anomalies` (copyright flag, hash
mismatch, stuck upload), the receipt says why — fix the delivery and drop a
new manifest with a new id; nothing is deleted.

## What you must NOT do

* Do not upload to YouTube yourself, from any session. One door to the
  channel: the posting agent, with receipts.
* Do not edit someone else's manifest; corrections are new files.
* Do not put tokens, session cookies or the pc-eye URL in a manifest or
  anywhere else in this repo.
