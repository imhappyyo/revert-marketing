#!/usr/bin/env python3
"""
Generate TikTok/Reels-ready video via the Kling AI API Platform (text2video).

Reads KLING_API_KEY from env / marketing/.env. Auth is a plain bearer token
(Kling's current API Platform issues one API key per project — no separate
secret key, no JWT signing).

CLI:  python3 genvideo.py "<hook/brief>" out.mp4 [--ratio 9:16] [--duration 5]
                                          [--model kling-v2.5-turbo] [--negative "..."]

Importable:  from genvideo import generate; generate(prompt, "out.mp4", aspect_ratio="9:16")

Stdlib only.
"""
import os, sys, json, time, argparse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE = "https://api.klingai.com"
POLL_INTERVAL = 10       # seconds between status checks
POLL_TIMEOUT = 600       # give up after 10 minutes


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _request(method, url, api_key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:500].decode(errors='replace')}") from e


def _dig(d, *keys):
    """Kling's response nests fields under 'data' in most docs but some newer
    endpoints return them top-level — check both so a schema drift doesn't
    silently break the pipeline."""
    for k in keys:
        if k in d:
            return d[k]
    return d.get("data", {}).get(keys[0]) if "data" in d else None


def generate(prompt, out_path, aspect_ratio="9:16", duration="5", model="kling-v2.5-turbo",
             negative_prompt="", cfg_scale=0.5, mode="std"):
    load_env()
    api_key = os.environ.get("KLING_API_KEY")
    if not api_key:
        raise RuntimeError("KLING_API_KEY not set (add it to marketing/.env)")
    base = os.environ.get("KLING_API_BASE", DEFAULT_BASE)

    submit = _request("POST", f"{base}/v1/videos/text2video", api_key, {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "cfg_scale": cfg_scale,
        "mode": mode,
        "aspect_ratio": aspect_ratio,
        "duration": str(duration),
    })
    data = submit.get("data", submit)
    task_id = data.get("task_id") or submit.get("task_id")
    if not task_id:
        raise RuntimeError(f"Kling submit failed (no task_id in response): {submit}")
    sys.stderr.write(f"[genvideo] submitted task {task_id}, polling...\n")

    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status = _request("GET", f"{base}/v1/videos/text2video/{task_id}", api_key)
        data = status.get("data", status)
        state = data.get("task_status") or data.get("status")
        if state in ("succeed", "success", "completed"):
            videos = (data.get("task_result") or {}).get("videos") or data.get("videos") or []
            if not videos:
                raise RuntimeError(f"task succeeded but no video in result: {data}")
            video_url = videos[0]["url"]
            urllib.request.urlretrieve(video_url, out_path)
            return out_path
        if state in ("failed", "error"):
            raise RuntimeError(f"Kling task failed: {data.get('task_status_msg', data)}")
        sys.stderr.write(f"[genvideo] status={state}, waiting {POLL_INTERVAL}s...\n")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"task {task_id} did not finish within {POLL_TIMEOUT}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate a vertical video with Kling from a text brief/hook.")
    ap.add_argument("prompt", help="video brief / hook, e.g. 'POV: your keyboard just rewrote your text message tone'")
    ap.add_argument("out", help="output path, e.g. out.mp4")
    ap.add_argument("--ratio", default="9:16", help="aspect ratio (default 9:16)")
    ap.add_argument("--duration", default="5", help="clip length in seconds (5 or 10)")
    ap.add_argument("--model", default="kling-v2.5-turbo", help="Kling model name")
    ap.add_argument("--negative", default="", help="negative prompt")
    args = ap.parse_args()

    path = generate(args.prompt, args.out, aspect_ratio=args.ratio, duration=args.duration,
                     model=args.model, negative_prompt=args.negative)
    print(f"✓ {path}")
