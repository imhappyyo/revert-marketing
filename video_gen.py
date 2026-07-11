#!/usr/bin/env python3
"""
Revert autonomous marketing — video step. Runs between engine.py and post.py.

PRIMARY PATH — real product demo (senior-marketing decision, July 10 2026):
the daily TikTok clip is a REAL screen recording of the app composed into a
branded frame with the day's hook (video_edit.py). For a keyboard app the
product demo IS the ad — no AI actors. Recordings live in assets/screencasts/
and rotate by date; drop new ones there any time.

FALLBACK — only if assets/screencasts/ is empty: Kling text-to-video with the
judged scene library in video_scenes.json (via genvideo.py). Cinematic b-roll,
but it cannot show the real UI, so it stays the backup.

The hook comes from today's batch.json (written by engine.py — same hook used
in the caption), so video and caption are never out of sync. youtube_shorts
reuses the same clip.

Graceful degradation: no recordings AND no KLING_API_KEY → silent no-op;
post.py queues video channels with "needs video clip" and the rest of the
pipeline is unaffected.

Output: marketing/outbox/<date>/video/tiktok.mp4 (+ youtube_shorts.mp4 copy)

Stdlib only (delegates to video_edit.py / genvideo.py).
"""
import os, sys, json, shutil, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
SCREENCAST_DIR = os.path.join(ROOT, "assets", "screencasts")

# Audience key -> a singular, castable on-camera person. The brand.json "who"
# strings are plural marketing copy ("People who freeze up...") and read as
# nonsense inside a cinematography prompt ("close-up on the face of People
# who..."), so scenes cast a concrete human instead.
VIDEO_CAST = {
    "dating":   "a nervous but charming young man in his mid-20s",
    "esl":      "a bright international student in her early 20s",
    "pros":     "a sharp, overworked professional woman in her early 30s",
    "anxious":  "an endearing overthinker in his early 20s",
    "learners": "a curious young woman in her 20s learning a new language",
}
DEFAULT_CAST = "a young adult on their phone"


def load_dotenv():
    p = os.path.join(ROOT, ".env")
    if not os.path.exists(p):
        return
    for line in open(p):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def latest_batch_path():
    import glob
    dirs = sorted(glob.glob(os.path.join(ROOT, "outbox", "*", "batch.json")))
    return dirs[-1] if dirs else None


def pick_scene(scenes, date_str):
    """Strict round-robin by date ordinal — deterministic (same batch date always
    maps to the same scene, so re-runs are idempotent) AND consecutive days are
    guaranteed to get different scenes, unlike a hash which clumps."""
    n = datetime.date.fromisoformat(date_str).toordinal()
    return scenes[n % len(scenes)]


def build_prompt(batch):
    """Returns (prompt, negative_prompt, scene_key) or None if no tiktok item."""
    brand = json.load(open(os.path.join(ROOT, "brand.json")))
    lib = json.load(open(os.path.join(ROOT, "video_scenes.json")))
    item = batch["items"].get("tiktok")
    if not item:
        return None
    angle_id = item.get("angle")
    angle = next((a for a in brand["angles"] if a["id"] == angle_id), None)
    hook = item.get("hook", "") or "quiet confidence, the reply that lands perfectly"
    idea = angle["idea"] if angle else "an AI keyboard that writes the perfect reply"
    who = VIDEO_CAST.get(item.get("audience"), DEFAULT_CAST)

    scene = pick_scene(lib["scenes"], batch["date"])
    prompt = scene["template"].format(who=who, idea=idea, hook=hook) + " " + lib["style_suffix"]
    return prompt, lib["negative_prompt"], scene["key"]


def pick_screencast(date_str):
    """Date-rotated pick from assets/screencasts/ (round-robin, idempotent)."""
    if not os.path.isdir(SCREENCAST_DIR):
        return None
    casts = sorted(f for f in os.listdir(SCREENCAST_DIR)
                   if f.lower().endswith((".mp4", ".mov")))
    if not casts:
        return None
    n = datetime.date.fromisoformat(date_str).toordinal()
    return os.path.join(SCREENCAST_DIR, casts[n % len(casts)])


def main():
    load_dotenv()
    batch_path = latest_batch_path()
    if not batch_path:
        print("[video_gen] no batch found — run engine.py first"); return
    batch = json.load(open(batch_path))
    bdir = os.path.dirname(batch_path)
    viddir = os.path.join(bdir, "video")
    os.makedirs(viddir, exist_ok=True)

    tiktok_path = os.path.join(viddir, "tiktok.mp4")
    if os.path.exists(tiktok_path):
        print(f"[video_gen] {tiktok_path} already exists — skipping"); return

    item = batch["items"].get("tiktok")
    if not item:
        print("[video_gen] no tiktok item in today's batch — skipping"); return
    hook = item.get("hook") or "the AI keyboard that reads the room"

    # CONTENT MIX (marketing decision, July 10 2026): every 3rd day = real
    # screen-recording demo (trust + product comprehension); other days =
    # Kling lifestyle clip branded in post with the REAL logo/hook/end-card
    # (video_edit.brand_full_bleed). Any failure falls back to the screencast.
    ordinal = datetime.date.fromisoformat(batch["date"]).toordinal()
    screencast = pick_screencast(batch["date"])
    want_screencast_day = (ordinal % 3 == 0) or not os.environ.get("KLING_API_KEY")

    def do_screencast():
        if not screencast:
            return False
        from video_edit import compose
        print(f"[video_gen] real-UI edit: {os.path.basename(screencast)}  hook: {hook}")
        try:
            compose(hook, screencast, tiktok_path)
            return True
        except Exception as e:
            print(f"[video_gen] screencast edit failed: {e}")
            return False

    def do_kling():
        if not os.environ.get("KLING_API_KEY"):
            return False
        built = build_prompt(batch)
        if not built:
            return False
        prompt, negative, scene_key = built
        from genvideo import generate
        from video_edit import brand_full_bleed
        import tempfile
        print(f"[video_gen] Kling scene: {scene_key}")
        raw = os.path.join(tempfile.mkdtemp(prefix="revkling_"), "raw.mp4")
        try:
            generate(prompt, raw, aspect_ratio="9:16", duration="5",
                     negative_prompt=negative)
            brand_full_bleed(hook, raw, tiktok_path)
            return True
        except Exception as e:
            print(f"[video_gen] Kling path failed: {e}")
            return False

    if want_screencast_day:
        ok = do_screencast() or do_kling()
    else:
        ok = do_kling() or do_screencast()
    if not ok:
        print("[video_gen] no video produced — tiktok/youtube_shorts stay queued")
        return

    yt_path = os.path.join(viddir, "youtube_shorts.mp4")
    shutil.copyfile(tiktok_path, yt_path)
    print(f"✓ {tiktok_path}\n✓ {yt_path} (reused)")


if __name__ == "__main__":
    main()
