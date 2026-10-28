# receipts/

One `<delivery_id>.json` per posted video, written by the posting agent
(schema in [POSTER.md](../POSTER.md)). A receipt is what makes a delivery
*done*: `scheduler.py` skips any delivery id that has one, and its absence
means the video gets re-planned. Receipts are never edited or deleted — a
correction is a new file (`d-0001-fix.json`) with a note pointing at the
original.
