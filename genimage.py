#!/usr/bin/env python3
"""
Generate marketing images with Nano Banana (Google Gemini image models).

Fills the `needs media` gap for Instagram, X, blog heroes, ASO mockups, and
short-form background frames. Reads REVERT_IMAGE_KEY from env / marketing/.env.

CLI:  python3 genimage.py "<prompt>" <out.png> [aspect]
      aspect is baked into the prompt (1:1 | 4:5 | 9:16 | 16:9). Default 1:1.

Importable:  from genimage import generate; generate(prompt, "out.png", "9:16")

Stdlib only.
"""
import os, sys, json, base64, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))

# Best-text-rendering first, then graceful fallback to classic Nano Banana.
MODELS = [m for m in [
    os.environ.get("REVERT_IMAGE_MODEL"),
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
] if m]

ASPECT_HINT = {
    "1:1":  "Square 1:1 composition.",
    "4:5":  "Vertical 4:5 portrait composition (Instagram feed).",
    "9:16": "Tall vertical 9:16 composition (full-screen phone / Reel / Story).",
    "16:9": "Wide 16:9 landscape composition.",
}


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def generate(prompt, out_path, aspect="1:1"):
    load_env()
    key = os.environ.get("REVERT_IMAGE_KEY")
    if not key:
        raise RuntimeError("REVERT_IMAGE_KEY not set (add it to marketing/.env)")
    full = f"{prompt}\n\n{ASPECT_HINT.get(aspect, '')}".strip()
    body = json.dumps({
        "contents": [{"parts": [{"text": full}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }).encode()
    last = None
    for model in MODELS:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        with open(out_path, "wb") as fh:
                            fh.write(base64.b64decode(inline["data"]))
                        return model
            last = f"{model}: no image in response"
        except urllib.error.HTTPError as e:
            last = f"{model}: HTTP {e.code} {e.read()[:200].decode(errors='replace')}"
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            last = f"{model}: {e}"
        sys.stderr.write(f"[genimage] {last}\n")
    raise RuntimeError(f"image generation failed — {last}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: genimage.py '<prompt>' <out.png> [1:1|4:5|9:16|16:9]"); sys.exit(2)
    prompt, out = sys.argv[1], sys.argv[2]
    aspect = sys.argv[3] if len(sys.argv) > 3 else "1:1"
    used = generate(prompt, out, aspect)
    print(f"✓ {out}  ({used}, {aspect})")
