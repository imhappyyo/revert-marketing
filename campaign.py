#!/usr/bin/env python3
"""
Generate the standard Revert marketing image set with Nano Banana, in one command.

    python3 campaign.py            # -> outbox/<today>/img/*.png

Brand-consistent prompts are built from brand.json (tagline, one-liner, a rotating
hook), so the visuals match the copy the engine wrote the same day. Drops files where
post.py / the QUEUE can pick them up.

Requires REVERT_IMAGE_KEY with a funded AI Studio project (see .env). Until funded,
each call returns 429 and this prints a clear, actionable message.

Stdlib only (delegates to genimage.generate).
"""
import os, sys, json, datetime
from genimage import generate

ROOT = os.path.dirname(os.path.abspath(__file__))
BRAND = json.load(open(os.path.join(ROOT, "brand.json")))
P = BRAND["product"]
SITE = P["links"]["site"]

# deep near-black brand bg + purple/blue spiral, matching the app icon
BRANDLOOK = ("Background deep near-black (#020208) with a subtle purple-to-blue gradient "
             "spiral motif. Apple-style product photography, dramatic soft studio lighting, "
             "premium, cinematic, generous negative space, crisp legible sans-serif text.")


def hook(salt=0):
    import hashlib
    d = datetime.date.today().isoformat()
    h = int(hashlib.sha1((d + str(salt)).encode()).hexdigest(), 16)
    return BRAND["hooks"][h % len(BRAND["hooks"])]


SET = [
    ("hero_9x16.png", "9:16",
     f"App marketing poster for 'Revert', an AI keyboard. A sleek iPhone held in one hand, "
     f"showing a chat thread with a minimal keyboard and three softly glowing AI reply cards "
     f"floating above it. Headline text reads exactly: '{P['tagline']}'. Footer text reads "
     f"exactly: '{SITE}'. {BRANDLOOK}"),
    ("before_after_4x5.png", "4:5",
     f"Split before/after social graphic for the AI keyboard 'Revert'. LEFT half labeled "
     f"'BEFORE' shows a flat awkward half-typed text. RIGHT half labeled 'AFTER' shows a "
     f"confident, warm reply in a chat bubble. Bottom caption reads exactly: '{P['tagline']}'. "
     f"{BRANDLOOK}"),
    ("square_ad_1x1.png", "1:1",
     f"Square app store / Instagram promo for 'Revert', an AI keyboard. Floating iPhone showing "
     f"three glowing tap-to-reply suggestion cards. Headline reads exactly: 'Stop typing.' and "
     f"'Start tapping.' on two lines. Small badge text reads exactly: 'Free on iOS & Android'. "
     f"{BRANDLOOK}"),
    ("short_frame_9x16.png", "9:16",
     f"Bold full-screen vertical hook frame for a short-form video. Huge centered text reads "
     f"exactly: '{hook()}'. Minimal, high-contrast, scroll-stopping. {BRANDLOOK}"),
    ("blog_hero_16x9.png", "16:9",
     f"Wide editorial blog hero image about texting and AI. A calm flat-lay of a phone showing a "
     f"friendly chat, soft props, no text. {BRANDLOOK}"),
]


def main():
    d = os.environ.get("REVERT_RUN_DATE", datetime.date.today().isoformat())
    outdir = os.path.join(ROOT, "outbox", d, "img")
    os.makedirs(outdir, exist_ok=True)
    ok, fail = 0, 0
    for name, aspect, prompt in SET:
        path = os.path.join(outdir, name)
        try:
            used = generate(prompt, path, aspect)
            print(f"  ✓ {name:24s} ({used}, {aspect})"); ok += 1
        except Exception as e:
            msg = str(e)
            if "429" in msg or "prepayment" in msg.lower():
                print("\n⚠ Image generation blocked: AI Studio prepayment credits depleted.")
                print("  Top up at https://ai.studio/projects then re-run: python3 campaign.py\n")
                sys.exit(1)
            print(f"  ✗ {name:24s} {msg[:120]}"); fail += 1
    print(f"\nDone: {ok} generated, {fail} failed -> outbox/{d}/img/")


if __name__ == "__main__":
    main()
