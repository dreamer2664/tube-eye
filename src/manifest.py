"""tube-eye — delivery manifest schema and validation.

A delivery manifest is the contract between a video producer (any agent, any
repo) and the posting division. One JSON file per video in deliveries/.
Validation is pure stdlib, side-effect free, and identical in CI and in
intake.py — so a producer can self-check before pushing.
"""

import json
import re

SCHEMA_VERSION = 1

ID_RE = re.compile(r"^d-\d{4}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

KINDS = ("video", "short")
VISIBILITIES = ("scheduled", "unlisted", "private", "public")

# YouTube hard limits, enforced here so Studio never rejects an upload.
TITLE_MAX = 100
DESCRIPTION_MAX = 5000
TAGS_TOTAL_MAX = 500
SHORT_MAX_SECONDS = 180


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate(m):
    """Return a list of human-readable error strings. Empty list == valid."""
    errors = []

    def err(msg):
        errors.append(msg)

    if not isinstance(m, dict):
        return ["manifest is not a JSON object"]

    vid = m.get("id")
    if not isinstance(vid, str) or not ID_RE.match(vid):
        err("id must look like 'd-0001' (d- followed by 4 digits)")

    title = m.get("title")
    if not isinstance(title, str) or not title.strip():
        err("title is required")
    elif len(title) > TITLE_MAX:
        err(f"title is {len(title)} chars; YouTube allows {TITLE_MAX}")

    desc = m.get("description")
    if not isinstance(desc, str) or not desc.strip():
        err("description is required")
    elif len(desc) > DESCRIPTION_MAX:
        err(f"description is {len(desc)} chars; YouTube allows {DESCRIPTION_MAX}")

    tags = m.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        err("tags must be a list of strings")
    else:
        total = sum(len(t) for t in tags) + max(len(tags) - 1, 0)
        if total > TAGS_TOTAL_MAX:
            err(f"tags total {total} chars; YouTube allows {TAGS_TOTAL_MAX}")

    for field in ("producer", "source_repo"):
        if not isinstance(m.get(field), str) or not m.get(field, "").strip():
            err(f"{field} is required")

    kind = m.get("kind")
    if kind not in KINDS:
        err(f"kind must be one of {KINDS}")

    visibility = m.get("visibility")
    if visibility not in VISIBILITIES:
        err(f"visibility must be one of {VISIBILITIES}")
    if visibility == "public" and m.get("approved_by_human") is not True:
        err("visibility 'public' (publish now) requires approved_by_human: true "
            "— a human decision, recorded in the manifest")

    if not isinstance(m.get("synthetic_media_disclosure"), bool):
        err("synthetic_media_disclosure must be true or false "
            "(YouTube's altered-content question is answered from this)")

    video = m.get("video")
    if not isinstance(video, dict):
        err("video block is required: {url, sha256, bytes, duration_s}")
    else:
        if not (isinstance(video.get("url"), str) and video["url"].startswith("https://")):
            err("video.url must be an https:// URL")
        if not (isinstance(video.get("sha256"), str) and SHA256_RE.match(video.get("sha256", ""))):
            err("video.sha256 must be 64 lowercase hex chars")
        if not (isinstance(video.get("bytes"), int) and video["bytes"] > 0):
            err("video.bytes must be a positive integer")
        dur = video.get("duration_s")
        if not (isinstance(dur, (int, float)) and dur > 0):
            err("video.duration_s must be a positive number")
        elif kind == "short" and dur > SHORT_MAX_SECONDS:
            err(f"kind 'short' but duration_s is {dur}; a Short is <= {SHORT_MAX_SECONDS}s")

    thumb = m.get("thumbnail")
    if kind == "video":
        if not isinstance(thumb, dict):
            err("thumbnail block is required for kind 'video': {url, sha256}")
        else:
            if not (isinstance(thumb.get("url"), str) and thumb["url"].startswith("https://")):
                err("thumbnail.url must be an https:// URL")
            if not (isinstance(thumb.get("sha256"), str) and SHA256_RE.match(thumb.get("sha256", ""))):
                err("thumbnail.sha256 must be 64 lowercase hex chars")

    captions = m.get("captions")
    if captions is not None:
        if not isinstance(captions, dict):
            err("captions must be an object: {url, language}")
        else:
            if not (isinstance(captions.get("url"), str) and captions["url"].startswith("https://")):
                err("captions.url must be an https:// URL")
            if not (isinstance(captions.get("language"), str) and captions["language"].strip()):
                err("captions.language is required when captions are present")

    dp = m.get("desired_publish_at")
    if dp is not None and not isinstance(dp, str):
        err("desired_publish_at must be an ISO-8601 string or null")

    return errors
