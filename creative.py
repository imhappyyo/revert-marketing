#!/usr/bin/env python3
"""
Revert creative generator — code-rendered, on-brand marketing graphics.

No external AI service, no credits, no quota: builds branded HTML and renders it to
PNG with headless Chrome. Text is always pixel-perfect and on-brand (real fonts, real
gradients) — which beats image-diffusion for a UI product whose ads carry headlines.

    python3 creative.py            # -> outbox/<today>/img/*.png  (full set)
    python3 creative.py hook       # -> just the daily short-form hook frame

Copy is pulled from brand.json (tagline, sample replies, a rotating daily hook) so the
visuals match the day's copy. post.py picks up the PNGs from outbox/<date>/img/.

Stdlib only (+ headless Chrome).
"""
import os, sys, json, hashlib, datetime, subprocess, tempfile, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
BRAND = json.load(open(os.path.join(ROOT, "brand.json")))
P = BRAND["product"]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BG = "#020208"
ACCENT = "#C96442"        # coral CTA
INK = "#F4F1EC"

SAMPLE_REPLIES = [
    "A hike sounds amazing — Saturday morning?",
    "Yes! There's a beautiful loop at Muir Woods 😊",
    "Tennessee Valley trail — easy walk, unreal views.",
]


def daily_hook():
    d = os.environ.get("REVERT_RUN_DATE", datetime.date.today().isoformat())
    h = int(hashlib.sha1(d.encode()).hexdigest(), 16)
    return BRAND["hooks"][h % len(BRAND["hooks"])]


def spiral_svg(size=120):
    # the Revert brand mark: purple->blue gradient spiral
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 100 100" fill="none">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#7C5CFF"/><stop offset="1" stop-color="#3FA9FF"/>
      </linearGradient></defs>
      <path d="M50 8a42 42 0 1 1-29.7 12.3" stroke="url(#g)" stroke-width="9" stroke-linecap="round" fill="none"/>
      <path d="M50 24a26 26 0 1 0 18.4 7.6" stroke="url(#g)" stroke-width="9" stroke-linecap="round" fill="none" opacity="0.85"/>
      <circle cx="50" cy="50" r="9" fill="url(#g)"/>
    </svg>"""


def product_html(w, h, headline, subline):
    big = max(34, int(w * 0.085))
    cards = "".join(
        f'<div class="card" style="opacity:{1-0.18*i}">{r}'
        f'<span class="tap"></span></div>' for i, r in enumerate(SAMPLE_REPLIES))
    return f"""<!doctype html><meta charset="utf-8"><style>
    *{{margin:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
    html,body{{width:{w}px;height:{h}px;overflow:hidden}}
    body{{background:
      radial-gradient(900px 700px at 85% -10%, rgba(124,92,255,.28), transparent 60%),
      radial-gradient(800px 600px at -10% 110%, rgba(63,169,255,.22), transparent 55%),
      {BG};
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;
      color:{INK};display:flex;flex-direction:column;padding:{int(w*0.075)}px}}
    .top{{display:flex;align-items:center;gap:14px;font-weight:700;letter-spacing:.5px;font-size:{int(w*0.032)}px}}
    .top svg{{width:{int(w*0.06)}px;height:{int(w*0.06)}px}}
    .h{{font-size:{big}px;font-weight:800;line-height:1.02;letter-spacing:-.02em;margin-top:{int(h*0.04)}px}}
    .h .dim{{color:#9a96a8}}
    .sub{{font-size:{int(w*0.034)}px;color:#b9b5c4;margin-top:{int(h*0.018)}px;max-width:86%;line-height:1.35}}
    .phone{{margin:{int(h*0.045)}px auto 0;width:{int(w*0.62)}px;flex:1;
      background:linear-gradient(180deg,#0d0d16,#08080f);border:1px solid #20202e;
      border-radius:{int(w*0.06)}px;box-shadow:0 30px 80px rgba(0,0,0,.6);
      padding:{int(w*0.05)}px {int(w*0.045)}px;display:flex;flex-direction:column;justify-content:flex-end;gap:{int(w*0.028)}px}}
    .card{{background:linear-gradient(180deg,#16121f,#120f1a);border:1px solid #2a2440;
      border-radius:{int(w*0.035)}px;padding:{int(w*0.034)}px {int(w*0.04)}px;font-size:{int(w*0.03)}px;
      color:#e9e6f2;position:relative;box-shadow:0 0 26px rgba(124,92,255,.18)}}
    .tap{{position:absolute;right:{int(w*0.035)}px;top:50%;transform:translateY(-50%);
      width:{int(w*0.05)}px;height:{int(w*0.05)}px;border-radius:50%;
      background:radial-gradient(circle at 40% 35%,#7C5CFF,#3FA9FF)}}
    .foot{{display:flex;align-items:center;justify-content:space-between;margin-top:{int(h*0.03)}px}}
    .pill{{background:{ACCENT};color:#1a0f0a;font-weight:700;font-size:{int(w*0.028)}px;
      padding:{int(w*0.022)}px {int(w*0.04)}px;border-radius:999px}}
    .url{{font-size:{int(w*0.03)}px;color:#cfcbd9;font-weight:600}}
    </style>
    <div class="top">{spiral_svg()}<span>REVERT</span></div>
    <div class="h">{headline}</div>
    <div class="sub">{subline}</div>
    <div class="phone">{cards}</div>
    <div class="foot"><span class="pill">Free · iOS &amp; Android</span><span class="url">gorevert.com</span></div>
    """


def hook_html(w, h, hook):
    return f"""<!doctype html><meta charset="utf-8"><style>
    *{{margin:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
    html,body{{width:{w}px;height:{h}px;overflow:hidden}}
    body{{background:radial-gradient(700px 700px at 50% 20%,rgba(124,92,255,.30),transparent 60%),{BG};
      font-family:-apple-system,'SF Pro Display','Helvetica Neue',Arial,sans-serif;color:{INK};
      display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;
      padding:{int(w*0.1)}px}}
    .hook{{font-size:{int(w*0.085)}px;font-weight:800;line-height:1.08;letter-spacing:-.02em}}
    .brand{{position:absolute;bottom:{int(h*0.06)}px;display:flex;align-items:center;gap:12px;
      font-weight:700;letter-spacing:.5px;font-size:{int(w*0.034)}px}}
    .brand svg{{width:{int(w*0.07)}px;height:{int(w*0.07)}px}}
    </style>
    <div class="hook">{hook}</div>
    <div class="brand">{spiral_svg()}<span>REVERT · gorevert.com</span></div>
    """


def render(html, out_png, w, h):
    """Render HTML to PNG via headless Chrome.

    Hard-won flags:
      --headless=old   : the reliable one-shot screenshot mode (=new writes then hangs).
      unique profile   : avoids handing off to the user's running Chrome / lock conflicts.
      NO --force-device-scale-factor : it hangs the screenshot. 1080px = native social res.
    Chrome occasionally lingers after writing; we wait, then kill, then verify the PNG.
    """
    if not os.path.exists(CHROME):
        raise RuntimeError("Google Chrome not found (needed for rendering)")
    if os.path.exists(out_png):
        os.unlink(out_png)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html); src = f.name
    profile = tempfile.mkdtemp(prefix="revcr_")
    proc = subprocess.Popen(
        [CHROME, "--headless=old", "--disable-gpu", "--hide-scrollbars",
         f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
         f"--screenshot={out_png}", f"--window-size={w},{h}", f"file://{src}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=45)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        os.unlink(src)
        shutil.rmtree(profile, ignore_errors=True)
    # verify a real PNG was written (8-byte PNG signature)
    if not (os.path.exists(out_png) and os.path.getsize(out_png) > 1000
            and open(out_png, "rb").read(8) == b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"render failed — no valid PNG at {out_png}")
    return out_png


TAG1, TAG2 = "Stop typing.", "Start tapping."
HEAD = f'{TAG1}<br><span class="dim">{TAG2}</span>'
SUB = "Screenshot your chat. The AI writes 3 replies. Tap one."

FORMATS = [
    ("instagram_4x5", 1080, 1350, "product"),
    ("story_9x16",    1080, 1920, "product"),
    ("square_1x1",    1080, 1080, "product"),
    ("x_card_16x9",   1600,  900, "product"),
    ("hook_9x16",     1080, 1920, "hook"),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    d = os.environ.get("REVERT_RUN_DATE", datetime.date.today().isoformat())
    outdir = os.path.join(ROOT, "outbox", d, "img")
    os.makedirs(outdir, exist_ok=True)
    hook = daily_hook()
    n = 0
    for name, w, h, mode in FORMATS:
        if only and only not in name:
            continue
        html = hook_html(w, h, hook) if mode == "hook" else product_html(w, h, HEAD, SUB)
        out = os.path.join(outdir, f"{name}.png")
        render(html, out, w, h)
        print(f"  ✓ {name:16s} {w}x{h} -> outbox/{d}/img/{name}.png")
        n += 1
    print(f"\n{n} graphic(s) rendered (native social res) -> outbox/{d}/img/")


if __name__ == "__main__":
    main()
