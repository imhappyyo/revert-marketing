#!/usr/bin/env python3
"""
Revert screencast composer — turns REAL screen recordings into TikTok-ready ads.

Strategy (senior-marketing call): for a keyboard app the product demo IS the ad.
No AI-generated actors — the daily video is the actual app UI in action:

  ┌──────────────────────────┐
  │   HOOK TEXT (daily)      │   branded dark frame, violet glows
  │ ┌──────────────────────┐ │
  │ │                      │ │
  │ │   REAL SCREENCAST    │ │   rounded window, 1.25x pacing
  │ │   (assets/screencasts│ │
  │ │    rotated by date)  │ │
  │ └──────────────────────┘ │
  │  Revert · gorevert.com   │
  └──────────────────────────┘  + 2s brand end-card (spiral, tagline, CTA)

Drop more recordings into assets/screencasts/ any time — they rotate daily.
Optional: drop a royalty-free .mp3 into assets/music/ to score the edit.

CLI:  python3 video_edit.py "<hook text>" <screencast.mp4> <out.mp4>
Importable:  from video_edit import compose

Stdlib only (+ headless Chrome for overlays, ffmpeg for the edit).
"""
import os, sys, json, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
BRAND = json.load(open(os.path.join(ROOT, "brand.json")))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W, H = 1080, 1920
FPS = 30
SPEED = 1.25          # pacing: trims dead "thinking..." time without looking rushed
ENDCARD_SECS = 2.0

BG = "#020208"
INK = "#F4F1EC"


def ffmpeg_bin():
    for c in (shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("ffmpeg not found (brew install ffmpeg)")


def ffprobe_bin():
    for c in (shutil.which("ffprobe"), "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("ffprobe not found")


def probe(path):
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration", "-of", "json", path],
        capture_output=True, text=True, check=True)
    s = json.loads(out.stdout)["streams"][0]
    has_audio = bool(subprocess.run(
        [ffprobe_bin(), "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True).stdout.strip())
    return int(s["width"]), int(s["height"]), float(s.get("duration") or 0), has_audio


def render_png(html, out_png, transparent=False):
    """Headless-Chrome HTML->PNG (creative.py's hard-won flags: --headless=old,
    unique profile, no force-device-scale-factor)."""
    if not os.path.exists(CHROME):
        raise RuntimeError("Google Chrome not found (needed for overlay rendering)")
    if os.path.exists(out_png):
        os.unlink(out_png)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html); src = f.name
    profile = tempfile.mkdtemp(prefix="revve_")
    args = [CHROME, "--headless=old", "--disable-gpu", "--hide-scrollbars",
            f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
            f"--screenshot={out_png}", f"--window-size={W},{H}", f"file://{src}"]
    if transparent:
        args.insert(1, "--default-background-color=00000000")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=45)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        os.unlink(src)
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(out_png) or os.path.getsize(out_png) == 0:
        raise RuntimeError("Chrome produced no PNG")
    return out_png


def spiral_svg(size=120):
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 100 100" fill="none">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#7C5CFF"/><stop offset="1" stop-color="#3FA9FF"/>
      </linearGradient></defs>
      <path d="M50 8a42 42 0 1 1-29.7 12.3" stroke="url(#g)" stroke-width="9" stroke-linecap="round" fill="none"/>
      <path d="M50 24a26 26 0 1 0 18.4 7.6" stroke="url(#g)" stroke-width="9" stroke-linecap="round" fill="none" opacity="0.85"/>
      <circle cx="50" cy="50" r="9" fill="url(#g)"/>
    </svg>"""


def window_geometry(vid_w, vid_h):
    """Fit the recording into the frame leaving room for hook (top) and pill
    (bottom). Returns (x, y, w, h) of the video window, even-dimensioned."""
    top, bottom, side = 320, 150, 60
    max_h = H - top - bottom
    max_w = W - 2 * side
    scale = min(max_w / vid_w, max_h / vid_h)
    w = int(vid_w * scale) // 2 * 2
    h = int(vid_h * scale) // 2 * 2
    x = (W - w) // 2
    y = top + (max_h - h) // 2
    return x, y, w, h


def frame_html(hook, x, y, w, h):
    """Branded frame with a TRANSPARENT rounded window (box-shadow spotlight
    trick) — the real screencast shows through underneath."""
    r = 46
    return f"""<!doctype html><meta charset="utf-8"><style>
    *{{margin:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
    html,body{{width:{W}px;height:{H}px;overflow:hidden;background:transparent}}
    .win{{position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;
      border-radius:{r}px;background:transparent;
      box-shadow:0 0 0 9999px {BG};}}
    .glowA,.glowB{{position:absolute;border-radius:50%;filter:blur(2px);z-index:2;pointer-events:none}}
    .glowA{{left:-180px;top:-160px;width:760px;height:640px;
      background:radial-gradient(closest-side, rgba(124,92,255,.32), transparent)}}
    .glowB{{right:-160px;bottom:-140px;width:700px;height:600px;
      background:radial-gradient(closest-side, rgba(63,169,255,.22), transparent)}}
    .ring{{position:absolute;left:{x-3}px;top:{y-3}px;width:{w+6}px;height:{h+6}px;
      border-radius:{r+3}px;border:3px solid rgba(124,92,255,.55);
      box-shadow:0 0 44px rgba(124,92,255,.45), inset 0 0 22px rgba(124,92,255,.18);z-index:3}}
    .hook{{position:absolute;left:60px;right:60px;top:96px;z-index:4;text-align:center;
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;
      font-size:64px;font-weight:800;line-height:1.08;letter-spacing:-.5px;color:{INK};
      text-shadow:0 4px 30px rgba(0,0,0,.8)}}
    .pill{{position:absolute;left:50%;transform:translateX(-50%);bottom:52px;z-index:4;
      display:flex;align-items:center;gap:14px;padding:16px 30px;border-radius:999px;
      background:rgba(18,15,26,.92);border:1px solid #2a2440;
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;
      font-size:30px;font-weight:700;color:{INK}}}
    .pill svg{{width:38px;height:38px}}
    .pill .dim{{color:#9a96a8;font-weight:600}}
    </style>
    <div class="win"></div>
    <div class="glowA"></div><div class="glowB"></div>
    <div class="ring"></div>
    <div class="hook">{hook}</div>
    <div class="pill">{spiral_svg(38)} Revert <span class="dim">· gorevert.com</span></div>"""


def endcard_html():
    tag = BRAND["product"]["tagline"]
    return f"""<!doctype html><meta charset="utf-8"><style>
    *{{margin:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
    html,body{{width:{W}px;height:{H}px;overflow:hidden}}
    body{{background:
      radial-gradient(900px 700px at 85% -10%, rgba(124,92,255,.30), transparent 60%),
      radial-gradient(800px 600px at -10% 110%, rgba(63,169,255,.22), transparent 55%),
      {BG};
      display:flex;flex-direction:column;align-items:center;justify-content:center;gap:46px;
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;color:{INK}}}
    .tag{{font-size:84px;font-weight:800;letter-spacing:-1px;text-align:center;line-height:1.05;max-width:900px}}
    .free{{font-size:38px;color:#b9b5c4;font-weight:600}}
    .cta{{font-size:42px;font-weight:800;padding:26px 66px;border-radius:999px;
      background:linear-gradient(90deg,#7C5CFF,#3FA9FF);color:#fff}}
    </style>
    {spiral_svg(190)}
    <div class="tag">{tag}</div>
    <div class="free">Free on iOS &amp; Android · 50 replies a day</div>
    <div class="cta">gorevert.com</div>"""


def overlay_html(hook, with_pill=True):
    """Full-bleed branding overlay for AI-generated clips: readability scrims,
    hook headline top, logo pill bottom. Transparent everywhere else."""
    pill = f"""<div class="pill">{spiral_svg(38)} Revert <span class="dim">· gorevert.com</span></div>""" if with_pill else ""
    return f"""<!doctype html><meta charset="utf-8"><style>
    *{{margin:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
    html,body{{width:{W}px;height:{H}px;overflow:hidden;background:transparent}}
    .scrimT{{position:absolute;left:0;top:0;right:0;height:420px;
      background:linear-gradient(180deg, rgba(2,2,8,.82), rgba(2,2,8,0))}}
    .scrimB{{position:absolute;left:0;bottom:0;right:0;height:260px;
      background:linear-gradient(0deg, rgba(2,2,8,.72), rgba(2,2,8,0))}}
    .hook{{position:absolute;left:60px;right:60px;top:96px;text-align:center;
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;
      font-size:64px;font-weight:800;line-height:1.08;letter-spacing:-.5px;color:{INK};
      text-shadow:0 4px 30px rgba(0,0,0,.85)}}
    .pill{{position:absolute;left:50%;transform:translateX(-50%);bottom:52px;
      display:flex;align-items:center;gap:14px;padding:16px 30px;border-radius:999px;
      background:rgba(18,15,26,.92);border:1px solid #2a2440;
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;
      font-size:30px;font-weight:700;color:{INK}}}
    .pill svg{{width:38px;height:38px}}
    .pill .dim{{color:#9a96a8;font-weight:600}}
    </style>
    <div class="scrimT"></div><div class="scrimB"></div>
    <div class="hook">{hook}</div>
    {pill}"""


def brand_full_bleed(hook, clip, out_path, workdir=None):
    """Brand an AI-generated (or any full-frame 9:16) clip: scale to cover
    1080x1920, overlay hook + logo pill, append the 2s end card. This is how
    Kling clips get the REAL logo — AI never has to (and can't) render it."""
    ff = ffmpeg_bin()
    vid_w, vid_h, dur, has_audio = probe(clip)
    wd = workdir or tempfile.mkdtemp(prefix="revedit_")
    over_png = render_png(overlay_html(hook), os.path.join(wd, "overlay.png"), transparent=True)
    end_png = render_png(endcard_html(), os.path.join(wd, "endcard.png"))

    total = dur + ENDCARD_SECS
    music = find_music()
    # scale-to-cover then center-crop so any near-9:16 source fills the frame
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},fps={FPS}[vid];"
        f"[vid][1:v]overlay=0:0[main];"
        f"[2:v]fps={FPS},scale={W}:{H}[end];"
        f"[main][end]concat=n=2:v=1:a=0[v]"
    )
    cmd = [ff, "-y", "-v", "error",
           "-i", clip,
           "-loop", "1", "-t", f"{dur:.3f}", "-i", over_png,
           "-loop", "1", "-t", str(ENDCARD_SECS), "-i", end_png]
    if music:
        fc += f";[3:a]atrim=0:{total:.3f},afade=t=out:st={max(0, total-1.2):.3f}:d=1.2[a]"
        cmd += ["-stream_loop", "-1", "-i", music]
        amap = ["-map", "[a]"]
    elif has_audio:
        fc += (f";aevalsrc=0:d={ENDCARD_SECS}:s=44100[sil];"
               f"[0:a][sil]concat=n=2:v=0:a=1[a]")
        amap = ["-map", "[a]"]
    else:
        amap = []
    cmd += ["-filter_complex", fc, "-map", "[v]"] + amap + [
        "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", out_path]
    subprocess.run(cmd, check=True)
    if not workdir:
        shutil.rmtree(wd, ignore_errors=True)
    return out_path


def find_music():
    d = os.path.join(ROOT, "assets", "music")
    if os.path.isdir(d):
        tracks = sorted(f for f in os.listdir(d) if f.lower().endswith((".mp3", ".m4a", ".wav")))
        if tracks:
            return os.path.join(d, tracks[0])
    return None


def compose(hook, screencast, out_path, workdir=None):
    """Build the final TikTok clip: framed real screencast + hook + end card."""
    ff = ffmpeg_bin()
    vid_w, vid_h, dur, has_audio = probe(screencast)
    x, y, w, h = window_geometry(vid_w, vid_h)
    wd = workdir or tempfile.mkdtemp(prefix="revedit_")
    frame_png = render_png(frame_html(hook, x, y, w, h), os.path.join(wd, "frame.png"), transparent=True)
    end_png = render_png(endcard_html(), os.path.join(wd, "endcard.png"))

    main_secs = dur / SPEED
    music = find_music()

    # video graph: black canvas -> screencast (sped, scaled, positioned) -> frame overlay
    fc = (
        f"color=c={BG}:s={W}x{H}:r={FPS}:d={main_secs:.3f}[bg];"
        f"[0:v]setpts=PTS/{SPEED},scale={w}:{h},fps={FPS}[vid];"
        f"[bg][vid]overlay={x}:{y}:shortest=1[comp];"
        f"[comp][1:v]overlay=0:0[main];"
        f"[2:v]fps={FPS},scale={W}:{H}[end];"
        f"[main][end]concat=n=2:v=1:a=0[v]"
    )
    total = main_secs + ENDCARD_SECS
    cmd = [ff, "-y", "-v", "error",
           "-i", screencast,                                            # 0: recording
           "-loop", "1", "-t", f"{main_secs:.3f}", "-i", frame_png,     # 1: branded frame
           "-loop", "1", "-t", str(ENDCARD_SECS), "-i", end_png]        # 2: end card

    if music:
        fc += f";[3:a]atrim=0:{total:.3f},afade=t=out:st={total-1.2:.3f}:d=1.2[a]"
        cmd += ["-stream_loop", "-1", "-i", music]
        amap = ["-map", "[a]"]
    elif has_audio:
        fc += (f";[0:a]atempo={SPEED}[sa];"
               f"aevalsrc=0:d={ENDCARD_SECS}:s=44100[sil];"
               f"[sa][sil]concat=n=2:v=0:a=1[a]")
        amap = ["-map", "[a]"]
    else:
        amap = []

    cmd += ["-filter_complex", fc, "-map", "[v]"] + amap + [
        "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", out_path]
    subprocess.run(cmd, check=True)
    if not workdir:
        shutil.rmtree(wd, ignore_errors=True)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: video_edit.py '<hook text>' <screencast.mp4> <out.mp4>"); sys.exit(2)
    compose(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"✓ {sys.argv[3]}")
