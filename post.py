#!/usr/bin/env python3
"""
Revert posting dispatcher — provider-agnostic auto-upload to all channels.

Two backends (pick with REVERT_POST_PROVIDER), both verified June 2026:

  upload_post  (DEFAULT, cheapest)  https://upload-post.com
      One API key, all channels. Takes DIRECT FILE UPLOADS (multipart) — no media
      hosting needed. Free to start (~10 uploads/mo), then ~$16/mo unlimited.
      Auth:  Authorization: Apikey <key>   Needs UPLOAD_POST_USER (profile name).

  ayrshare     (most mature, pricey)  https://ayrshare.com
      One API key, 13+ networks. Media must be a PUBLIC URL, so set REVERT_MEDIA_BASE
      (e.g. a Cloudflare R2 custom domain that serves the outbox). $149/mo (no free tier).

SAFETY: dry-run by default. Nothing publishes unless REVERT_POST_LIVE=1 AND the chosen
provider's key is set. Otherwise everything is written to outbox/<date>/QUEUE.md.

Video channels (TikTok / YouTube Shorts) stay queued until a real clip exists.
Reality checks (see SETUP.md): TikTok public auto-post needs the provider's audited
access; Reddit posts are subject to manual approval + subreddit mod rules; X strips URLs.

Stdlib only.
"""
import os, sys, json, glob, secrets, csv, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))

# Revert channel -> canonical platform + which rendered graphic to attach.
CHANNELS = {
    "x":              {"platform": "twitter",   "image": "x_card_16x9.png"},
    "instagram":      {"platform": "instagram", "image": "instagram_4x5.png"},
    "reddit":         {"platform": "reddit",    "image": "square_1x1.png", "reddit": True},
    "tiktok":         {"platform": "tiktok",    "video": True},
    "youtube_shorts": {"platform": "youtube",   "video": True},
}
# upload-post uses "x" where ayrshare uses "twitter"
UP_NAME = {"twitter": "x"}

# ── append-only performance ledger ────────────────────────────────────────────
PERF_CSV = os.path.join(ROOT, "performance.csv")
PERF_HEADER = ["date", "channel", "angle", "audience", "hook", "caption",
               "views", "likes", "clicks", "installs"]


def _existing_perf_keys():
    """Set of (date, channel) already logged, so re-runs don't duplicate rows."""
    keys = set()
    if not os.path.exists(PERF_CSV):
        return keys
    with open(PERF_CSV, newline="") as fh:
        r = csv.DictReader(fh)
        for row in r:
            keys.add((row.get("date", ""), row.get("channel", "")))
    return keys


def log_performance(rows):
    """Append rows ([date,channel,angle,audience,hook,caption]) with empty metric
    cells. Writes header once. Skips (date,channel) pairs already present."""
    if not rows:
        return 0
    existing = _existing_perf_keys()
    new = [r for r in rows if (r[0], r[1]) not in existing]
    if not new:
        return 0
    write_header = not os.path.exists(PERF_CSV) or os.path.getsize(PERF_CSV) == 0
    with open(PERF_CSV, "a", newline="") as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(PERF_HEADER)
        for r in new:
            w.writerow(list(r) + ["", "", "", ""])  # empty views,likes,clicks,installs
    return len(new)


def provider():
    return os.environ.get("REVERT_POST_PROVIDER", "upload_post").lower()


def provider_key():
    return os.environ.get("UPLOAD_POST_KEY") if provider() == "upload_post" else os.environ.get("AYRSHARE_KEY")


def load_dotenv():
    p = os.path.join(ROOT, ".env")
    if not os.path.exists(p):
        return
    for line in open(p):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def latest_batch():
    dirs = sorted(glob.glob(os.path.join(ROOT, "outbox", "*", "batch.json")))
    return dirs[-1] if dirs else None


def extract_caption(md_path):
    text = open(md_path).read()
    for line in text.splitlines():
        if line.strip().upper().startswith("CAPTION:"):
            return line.split(":", 1)[1].strip()
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.endswith(":"):
            return s
    return text.strip()[:280]


# ── upload-post adapter (multipart, direct file upload) ───────────────────────

def _multipart(fields, files):
    b = "----revert" + secrets.token_hex(12)
    body = bytearray()
    for name, val in fields:
        body += (f'--{b}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n').encode()
    for name, fname, data, ctype in files:
        body += (f'--{b}\r\nContent-Disposition: form-data; name="{name}"; '
                 f'filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n').encode()
        body += data + b"\r\n"
    body += (f'--{b}--\r\n').encode()
    return f"multipart/form-data; boundary={b}", bytes(body)


def upload_post(caption, platform, image_path, title=None, subreddit=None):
    key = os.environ["UPLOAD_POST_KEY"]
    user = os.environ.get("UPLOAD_POST_USER", "")
    fields = [("user", user), ("platform[]", UP_NAME.get(platform, platform)), ("description", caption)]
    if platform == "twitter":                      # X strips URLs in-body; surface the link as a reply
        fields.append(("first_comment", "Free on iOS & Android → gorevert.com"))
    if title:
        fields.append(("title", title))
    if subreddit:
        fields.append(("subreddit", subreddit))
    files, endpoint = [], "https://api.upload-post.com/api/upload_text"
    if image_path and os.path.exists(image_path):
        files = [("photos[]", os.path.basename(image_path), open(image_path, "rb").read(), "image/png")]
        endpoint = "https://api.upload-post.com/api/upload_photos"
    ct, body = _multipart(fields, files)
    req = urllib.request.Request(endpoint, data=body,
                                 headers={"Authorization": f"Apikey {key}", "Content-Type": ct})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def upload_post_video(caption, platform, video_path, title=None):
    key = os.environ["UPLOAD_POST_KEY"]
    user = os.environ.get("UPLOAD_POST_USER", "")
    fields = [
        ("user", user), ("platform[]", UP_NAME.get(platform, platform)),
        ("title", title or caption[:150]), ("description", caption),
        ("is_aigc", "true"),  # AI-generated-content disclosure (TikTok/YouTube policy)
    ]
    if platform == "tiktok":
        # Without post_mode, TikTok silently falls back to MEDIA_UPLOAD (Inbox/draft
        # mode) — video sits unpublished, no post_url, needs manual tap-to-post.
        # DIRECT_POST actually publishes. upload-post.com holds its own approved
        # TikTok Content Posting API integration (no per-account audit needed on
        # our end), so request full public visibility — NOT SELF_ONLY. (July 11:
        # every attempt that day landed in Inbox regardless of privacy_level —
        # confirmed via upload-post.com's own email to be a temporary TikTok
        # daily-active-user rate limit from repeated manual test runs, not an
        # audit/visibility restriction. Don't reintroduce SELF_ONLY on that theory.)
        fields.append(("post_mode", "DIRECT_POST"))
        fields.append(("privacy_level", "PUBLIC_TO_EVERYONE"))
    files = [("video", os.path.basename(video_path), open(video_path, "rb").read(), "video/mp4")]
    ct, body = _multipart(fields, files)
    req = urllib.request.Request("https://api.upload-post.com/api/upload", data=body,
                                 headers={"Authorization": f"Apikey {key}", "Content-Type": ct})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


# ── ayrshare adapter (JSON, needs public media URL) ───────────────────────────

def ayrshare(caption, platform, media_url, extra=None):
    key = os.environ["AYRSHARE_KEY"]
    payload = {"post": caption, "platforms": [platform]}
    if media_url:
        payload["mediaUrls"] = [media_url]
    if os.environ.get("AYRSHARE_PROFILE_KEY"):
        payload["profileKey"] = os.environ["AYRSHARE_PROFILE_KEY"]
    if extra:
        payload.update(extra)
    req = urllib.request.Request("https://api.ayrshare.com/api/post", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def public_url_for(local_path, date, subdir="img"):
    base = os.environ.get("REVERT_MEDIA_BASE")
    if base and local_path and os.path.exists(local_path):
        return f"{base.rstrip('/')}/{date}/{subdir}/{os.path.basename(local_path)}"
    return None


def main():
    load_dotenv()
    batch_path = sys.argv[1] if len(sys.argv) > 1 else latest_batch()
    if not batch_path:
        print("No batch found. Run engine.py first."); sys.exit(1)
    batch = json.load(open(batch_path))
    date, bdir = batch["date"], os.path.dirname(batch_path)
    imgdir = os.path.join(bdir, "img")
    prov = provider()
    live = os.environ.get("REVERT_POST_LIVE") == "1" and bool(provider_key())
    q = [f"# Posting queue — {date}  (provider: {prov})",
         ("LIVE posting ON." if live else
          f"Live posting OFF — copy/paste below, or set the {prov} key + REVERT_POST_LIVE=1.")]

    perf_rows = []
    for ch in batch["items"]:
        if ch not in CHANNELS:
            print(f"  · {ch:14s} non-aggregator (see {ch}.md)"); continue
        spec = CHANNELS[ch]
        item = batch["items"][ch]
        caption = item.get("caption") or extract_caption(os.path.join(bdir, f"{ch}.md"))
        platform = spec["platform"]

        ang = item.get("angle", "")
        aud = item.get("audience", "")
        hook = item.get("hook", "")
        perf_rows.append([date, ch, ang, aud, hook, caption])

        if spec.get("video"):
            local_video = os.path.join(bdir, "video", f"{ch}.mp4")
            if not os.path.exists(local_video):
                q += [f"\n## {ch} -> {platform}  (needs a video clip — video_gen.py hasn't produced one)", caption]
                print(f"  ⏸ {ch:14s} queued (needs video)"); continue

            if not live:
                q += [f"\n## {ch} -> {platform}   video: {os.path.basename(local_video)}", caption]
                print(f"  ⏸ {ch:14s} queued (dry-run)  video: {os.path.basename(local_video)}")
                continue

            try:
                if prov == "upload_post":
                    res = upload_post_video(caption, platform, local_video, item.get("hook") or caption[:150])
                else:
                    media_url = public_url_for(local_video, date, subdir="video")
                    if not media_url:
                        raise RuntimeError("set REVERT_MEDIA_BASE (public URL) for the ayrshare path")
                    res = ayrshare(caption, platform, media_url)
                # HONESTY CHECK: upload-post returns success:true even when TikTok
                # actually shunted the video to the app Inbox as an unpublished draft
                # (rate limit / non-DIRECT fallback) — a draft has ZERO public surface
                # and cannot get a single view. Don't report that as "POSTED". Detect
                # the tell-tale strings and flag it as NOT LIVE so run.log tells the truth.
                blob = json.dumps(res).lower()
                not_live = any(s in blob for s in ("inbox", "no public url", "still processing"))
                if not_live:
                    print(f"  ⚠ {ch:14s} NOT LIVE (Inbox/draft — needs manual publish in app)")
                    q += [f"\n## {ch} ⚠ NOT LIVE — landed in Inbox/draft, publish manually  {json.dumps(res)[:200]}"]
                else:
                    print(f"  ✓ {ch:14s} POSTED -> {platform}")
                    q += [f"\n## {ch} POSTED ✓  {json.dumps(res)[:200]}"]
            except Exception as e:
                # Catch EVERYTHING per-channel (was only urllib/RuntimeError — a raw
                # socket.timeout on a slow upload escaped it and crashed the whole run
                # mid-loop, silently skipping every channel after it: July 22, X timed
                # out and Instagram never posted). One channel's failure must never
                # abort the others.
                detail = e.read().decode(errors="replace")[:200] if hasattr(e, "read") else str(e)
                print(f"  ✗ {ch:14s} failed: {detail}")
                q += [f"\n## {ch} FAILED: {detail}", caption]
            continue

        local_img = os.path.join(imgdir, spec["image"]) if spec.get("image") else None
        img_name = os.path.basename(local_img) if local_img and os.path.exists(local_img) else "(none)"
        title = item.get("title") if spec.get("reddit") else None
        sub = item.get("subreddit", "sideproject") if spec.get("reddit") else None

        if not live:
            q += [f"\n## {ch} -> {platform}   img: {img_name}", caption]
            print(f"  ⏸ {ch:14s} queued (dry-run)  img: {img_name}")
            continue

        try:
            if prov == "upload_post":
                res = upload_post(caption, platform, local_img, title, sub)
            else:
                media_url = public_url_for(local_img, date)
                if spec.get("image") and not media_url:
                    raise RuntimeError("set REVERT_MEDIA_BASE (public URL) for the ayrshare path")
                extra = {"redditOptions": {"title": title, "subreddit": sub}} if spec.get("reddit") else None
                res = ayrshare(caption, platform, media_url, extra)
            print(f"  ✓ {ch:14s} POSTED -> {platform}")
            q += [f"\n## {ch} POSTED ✓  {json.dumps(res)[:200]}"]
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as e:
            detail = e.read().decode(errors="replace")[:200] if hasattr(e, "read") else str(e)
            print(f"  ✗ {ch:14s} failed: {detail}")
            q += [f"\n## {ch} FAILED: {detail}", caption]

    with open(os.path.join(bdir, "QUEUE.md"), "w") as fh:
        fh.write("\n".join(q) + "\n")
    n_logged = log_performance(perf_rows)
    print(f"\nQueue: {os.path.relpath(os.path.join(bdir, 'QUEUE.md'), ROOT)}  "
          f"(provider={prov}, live={live})  perf: +{n_logged} row(s) -> performance.csv")


if __name__ == "__main__":
    main()
