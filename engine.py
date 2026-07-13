#!/usr/bin/env python3
"""
Revert autonomous marketing engine.

Generates a fresh, ready-to-post content batch for every channel from brand.json.

Tiers of operation (graceful degradation — works at every tier):
  1. No keys at all      -> composes content from the brand hook/angle library (varied by date).
  2. LLM key present      -> generates net-new copy per channel via an OpenAI-compatible endpoint.
  3. + Higgsfield credits -> video/image prompts are emitted ready for the generate step.

Env vars (all optional):
  REVERT_LLM_BASE   default https://api.gorevert.com/v1   (Revert's own proxy)
  REVERT_LLM_KEY    bearer/app token for that endpoint
  REVERT_LLM_HEADER default "Authorization: Bearer"  (use "X-App-Token" for the Revert proxy)
  REVERT_LLM_MODEL  default gpt-4o-mini

Output: marketing/outbox/<YYYY-MM-DD>/<channel>.md  +  batch.json (machine-readable, for post.py)

Stdlib only. No pip installs.
"""
import os, sys, json, datetime, urllib.request, urllib.error, hashlib, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))
BRAND = json.load(open(os.path.join(ROOT, "brand.json")))


def load_env():
    """Load marketing/.env directly (values may contain spaces/colons that
    aren't valid shell syntax — e.g. 'Authorization: Bearer' — so this script
    no longer depends on run.sh bash-sourcing the file)."""
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def today():
    # date provided via env for deterministic/testable runs, else system date
    d = os.environ.get("REVERT_RUN_DATE")
    return d if d else datetime.date.today().isoformat()


def daynum(date_str):
    return int(hashlib.sha1(date_str.encode()).hexdigest(), 16)


def pick(lst, date_str, salt=0):
    return lst[(daynum(date_str) + salt) % len(lst)]


def rotate(lst, date_str, n, salt=0):
    start = (daynum(date_str) + salt) % len(lst)
    return [lst[(start + i) % len(lst)] for i in range(min(n, len(lst)))]


# ── deterministic angle/audience selection (single source of truth) ──────────
# Reuse the SAME salts the per-channel .md generators already use, so the angle we
# RECORD in batch.json matches what each channel renders. Channels that currently
# pick no angle get a fixed distinct salt here (stable, date-deterministic).
ANGLE_SALT = {
    "tiktok": 1, "x": 11, "reddit": 2, "youtube_shorts": 4, "blog": 5,
    "instagram": 3, "email": 6, "aso": 7,
}


def pick_angle(date_str, channel):
    """Return the brand angle dict this channel uses today (deterministic)."""
    return pick(BRAND["angles"], date_str, ANGLE_SALT.get(channel, 0))


def audience_who(key):
    """Human label for an audience key (falls back to the raw key)."""
    for a in BRAND["audiences"]:
        if a["key"] == key:
            return a["who"]
    return key


# ── trend-aware hashtags (deterministic daily rotation, stdlib-only) ─────────
# The brand library gives each channel a FIXED hashtag pool. Posting the whole
# pool, in the same order, every single day looks botted and gets down-ranked.
# rotate() already deterministically picks a date-dependent window of any list, so
# we use it to surface a fresh, ordered subset per channel per date. Same date =>
# same tags (reproducible), different dates => different tags (so they "vary").
# How many tags to surface per channel (platform-appropriate; <= pool size).
HASHTAG_COUNT = {
    "tiktok": 5, "instagram": 5, "youtube_shorts": 4, "x": 2,
}


_TREND_CACHE = {}


def _trend_tags(channel):
    """Optional timely hashtags via the configured LLM — only when REVERT_LLM_KEY is
    set (else []). Cached per channel per run so we make at most one call each."""
    if not os.environ.get("REVERT_LLM_KEY"):
        return []
    if channel in _TREND_CACHE:
        return _TREND_CACHE[channel]
    out = llm("You output ONLY two space-separated lowercase hashtags, nothing else.",
              f"Two currently-relevant, non-spammy hashtags for a {channel} post promoting "
              f"an AI keyboard that writes your text replies (texting, dating, productivity). "
              f"Just the hashtags, each starting with #.", 30)
    tags = [w for w in (out or "").split() if w.startswith("#")][:2]
    _TREND_CACHE[channel] = tags
    return tags


def hashtags(date_str, channel):
    """Date-rotating subset of the channel's pool, blended with 1-2 timely LLM tags
    when REVERT_LLM_KEY is set. Pure deterministic rotation otherwise (free, no key)."""
    pool = BRAND["channels"].get(channel, {}).get("hashtags", [])
    if not pool:
        return ""
    n = HASHTAG_COUNT.get(channel, len(pool))
    salt = ANGLE_SALT.get(channel, 0)  # two channels sharing a pool size still differ
    base = rotate(pool, date_str, n, salt)
    lowers = {b.lower() for b in base}
    timely = [t for t in _trend_tags(channel) if t.lower() not in lowers]
    return " ".join(base + timely)


# ── LLM (optional) ───────────────────────────────────────────────────────────

def llm(system, user, max_tokens=600):
    key = os.environ.get("REVERT_LLM_KEY")
    if not key:
        return None
    base = os.environ.get("REVERT_LLM_BASE", "https://api.gorevert.com/v1").rstrip("/")
    model = os.environ.get("REVERT_LLM_MODEL", "gpt-4o-mini")
    header = os.environ.get("REVERT_LLM_HEADER", "Authorization: Bearer")
    hname, _, hprefix = header.partition(":")
    hval = (hprefix.strip() + " " + key).strip() if hprefix.strip() else key
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", hname.strip(): hval})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.load(r)
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
        sys.stderr.write(f"[engine] LLM call failed ({e}); falling back to templates\n")
        return None


SYSTEM = (
    "You are the social media copywriter for Revert, an AI keyboard app. "
    "Voice: " + BRAND["voice"]["personality"] + " "
    "Never use these words: revolutionary, game-changer, unleash, supercharge. "
    "One idea per post. Concrete before/after beats adjectives. Output only the copy, no preamble."
)
PROD = BRAND["product"]


def llm_or(template, system, user, max_tokens=600):
    out = llm(system, user, max_tokens)
    return out if out else template


# ── per-channel generators ───────────────────────────────────────────────────

def gen_tiktok(d):
    angle = pick(BRAND["angles"], d, 1)
    hook = pick(BRAND["hooks"], d, 1)
    cta = pick(BRAND["ctas"], d, 1)
    tags = hashtags(d, "tiktok")
    template = textwrap.dedent(f"""\
    HOOK (0-1.5s, on-screen text): {hook}

    SCRIPT / STORYBOARD ({angle['idea']}):
      0.0s  Open on a phone, a chat thread with a tricky message visible.
      1.5s  Cut: screenshot taken (flash + shutter).
      3.0s  Switch to Revert keyboard — 3 reply cards animate in.
      5.0s  Finger taps the best reply; it drops into the text field.
      6.5s  Hit send. Recipient types back instantly. Satisfied nod.
      8.0s  End card: "{PROD['tagline']}"  + app icon.

    CAPTION: {hook} {cta}
    HASHTAGS: {tags}

    HIGGSFIELD VIDEO PROMPT (run when credits available):
      "Vertical 9:16 phone screen recording aesthetic, close-up of hands holding an
       iPhone, a messaging app, then a sleek minimal keyboard with three glowing reply
       suggestion cards sliding up, finger taps one, smooth UI motion, soft studio
       lighting, modern, clean, 8s, trending-ad style." """)
    user = (f"Write a 8-12s TikTok for Revert. Angle: {angle['idea']} "
            f"Audience: {next(a['who'] for a in BRAND['audiences'] if a['key']==angle['audience'])}. "
            f"Give: (1) on-screen HOOK, (2) a 5-beat shot list, (3) a caption with a CTA to gorevert.com, "
            f"(4) hashtags from this set: {tags}.")
    return llm_or(template, SYSTEM, user, 500)


def gen_x(d):
    posts = []
    for salt in range(3):
        hook = pick(BRAND["hooks"], d, 10 + salt)
        cta = pick(BRAND["ctas"], d, 10 + salt)
        posts.append(f"- {hook}\n  {PROD['one_liner']}\n  {cta}")
    template = "THREE TWEETS (post one per day):\n\n" + "\n\n".join(posts)
    angle = pick(BRAND["angles"], d, 11)
    user = (f"Write 3 standalone tweets for Revert (AI keyboard, gorevert.com). "
            f"Each <280 chars, distinct angle, casual lowercase, max 1 hashtag, 1 has a CTA. "
            f"Lean on this angle for one of them: {angle['idea']}")
    return llm_or(template, SYSTEM, user, 400)


def gen_reddit(d):
    angle = pick(BRAND["angles"], d, 2)
    template = textwrap.dedent(f"""\
    SUBREDDIT: r/sideproject (rotate: r/apple, r/productivity, r/languagelearning)
    TITLE: I built an AI keyboard that reads your chat screenshots and writes the reply — would love feedback

    BODY:
    Hey all — solo dev here. I kept freezing up on replies (dating apps, work DMs, texts in
    a language I'm still learning), so I built Revert: you screenshot a conversation, it reads
    the context on-device, and gives you 3 ready replies to tap. There's also a live translator
    and tone control.

    The part I cared about most: it's privacy-first. Screenshots are read on your phone with
    Apple's Vision framework — conversations are never stored or sent to a server to be logged.

    It's free (50 replies/day), iOS + Android: {PROD['links']['site']}

    Genuinely after feedback — what would make you actually keep a keyboard like this installed?

    [Reminder: read each sub's self-promo rules; engage in comments, don't drive-by post.]""")
    user = (f"Write a value-first Reddit post for r/sideproject from the solo maker of Revert "
            f"(AI keyboard, screenshot->reply, on-device privacy, free 50/day, {PROD['links']['site']}). "
            f"Honest, non-salesy, ends asking for feedback. Angle: {angle['idea']}. Give a TITLE and BODY.")
    return llm_or(template, SYSTEM, user, 450)


def gen_instagram(d):
    hook = pick(BRAND["hooks"], d, 3)
    cta = pick(BRAND["ctas"], d, 3)
    tags = hashtags(d, "instagram")
    template = textwrap.dedent(f"""\
    FORMAT: Reel (repurpose the TikTok cut) + a 3-slide before/after carousel.

    CAROUSEL:
      Slide 1: "{hook}"
      Slide 2: BEFORE — a flat, awkward draft text (screenshot mock).
      Slide 3: AFTER — the Revert reply that actually lands. "{PROD['tagline']}"

    CAPTION: {hook}\n\n{PROD['one_liner']}\n\n{cta}
    HASHTAGS: {tags}""")
    user = (f"Write an Instagram caption + a 3-slide before/after carousel concept for Revert. "
            f"Hook: '{hook}'. End with CTA to gorevert.com and these hashtags: {tags}")
    return llm_or(template, SYSTEM, user, 400)


def gen_youtube(d):
    angle = pick(BRAND["angles"], d, 4)
    template = textwrap.dedent(f"""\
    TITLE: This AI Keyboard Writes Your Texts For You (Revert) #Shorts
    DESCRIPTION: Screenshot any chat, tap a reply. Revert is the AI keyboard for iPhone &
    Android. Free, on-device privacy. {PROD['links']['site']}
    Repurpose the vertical TikTok cut; add a keyword-rich title.""")
    user = (f"Write a YouTube Shorts title (keyword-rich, <70 chars) and 2-line description "
            f"for a Revert demo. Angle: {angle['idea']}. Include {PROD['links']['site']}.")
    return llm_or(template, SYSTEM, user, 200)


def gen_email(d):
    template = textwrap.dedent(f"""\
    SUBJECT: Your first one-tap reply is waiting
    PREVIEW: Screenshot a chat. Tap. Done.

    Hey —

    You installed Revert. One thing left: make it the keyboard that does the talking.

    1. Open any chat and take a screenshot.
    2. Switch to the Revert keyboard.
    3. Three replies are already waiting. Tap the one that fits.

    That's it. 50 replies a day are on us, free.

    — The Revert team
    {PROD['links']['site']}""")
    user = ("Write a short plain-text activation email for someone who just installed Revert "
            "but hasn't enabled the keyboard yet. Subject + preview + body, warm, 90 words max, "
            "3-step how-to, CTA to open the app.")
    return llm_or(template, SYSTEM, user, 350)


def gen_aso(d):
    f = {x["key"]: x for x in BRAND["features"]}
    template = textwrap.dedent(f"""\
    APP STORE
      Title (30c):    Revert: AI Keyboard
      Subtitle (30c): Reply, Translate, One Tap
      Keywords (100c): ai keyboard,reply,texting,translate,chat,smart,autocorrect,dating,dm,gpt,assistant,tone
      Promo text: Screenshot a chat, tap the perfect reply. Private, on-device, free.

    DESCRIPTION (both stores):
    {PROD['one_liner']}

    • {f['replies']['blurb']}
    • {f['translator']['blurb']}
    • {f['tone']['blurb']}
    • {f['privacy']['blurb']}

    Free: 50 AI replies a day. Pro: unlimited, {PROD['pricing']['pro_monthly']} or {PROD['pricing']['pro_annual']}.
    {PROD['tagline']}

    PLAY STORE
      Title (30c):       Revert: AI Keyboard
      Short desc (80c):  AI keyboard that reads your chat and writes the perfect reply. One tap.""")
    return template  # ASO is deterministic; not LLM-randomized to keep listings stable


def gen_blog(d):
    angle = pick(BRAND["angles"], d, 5)
    template = textwrap.dedent(f"""\
    TITLE: How to Always Know What to Text Back (Without Overthinking It)
    TARGET KEYWORD: what to text back
    SLUG: what-to-text-back

    Intro: We've all stared at a message for ten minutes. This post covers the psychology of
    reply-paralysis and a faster way through it.

    H2: Why "what do I say?" freezes you
    H2: The 3-second rule for replies
    H2: Let context do the work (screenshot -> reply)
    H2: When to sound warmer, firmer, or funnier
    H2: Texting in another language without sounding like a robot

    CTA: Revert turns any chat screenshot into 3 ready replies — free on iOS & Android.
    {PROD['links']['site']}

    [Write full 900-1200 word draft below from this outline.]""")
    user = (f"Write an 900-1100 word SEO blog post for gorevert.com. Target keyword: 'what to text back'. "
            f"Helpful, not salesy; H2 sections; weave in Revert (screenshot->reply AI keyboard) naturally "
            f"with one CTA at the end to {PROD['links']['site']}. Angle: {angle['idea']}. Markdown.")
    return llm_or(template, SYSTEM, user, 1500)


GENERATORS = {
    "tiktok": gen_tiktok, "x": gen_x, "reddit": gen_reddit, "instagram": gen_instagram,
    "youtube_shorts": gen_youtube, "email": gen_email, "aso": gen_aso, "blog": gen_blog,
}


def captions(d):
    """Clean, postable caption per auto-post channel — built directly from the brand
    library (not scraped from the human .md briefs), so what gets posted is always tidy."""
    one = PROD["one_liner"]
    tt = hashtags(d, "tiktok")
    ig = hashtags(d, "instagram")
    yt = hashtags(d, "youtube_shorts")
    xt = hashtags(d, "x")  # X: 1-2 hashtags measurably beats zero (+21% engagement,
                            # 2026 data) but 3+ actively hurts reach — stay at 2 max.
    h_x  = pick(BRAND['hooks'], d, 10)
    h_ig = pick(BRAND['hooks'], d, 3)
    h_tt = pick(BRAND['hooks'], d, 1)
    return {
        "x":              {"hook": h_x,  "caption": f"{h_x}\n\n{one}\n\n{pick(BRAND['ctas'], d, 10)} {xt}"},
        "instagram":      {"hook": h_ig, "caption": f"{h_ig}\n\n{one}\n\n{pick(BRAND['ctas'], d, 3)}\n\n{ig}"},
        "tiktok":         {"hook": h_tt, "caption": f"{h_tt} {pick(BRAND['ctas'], d, 1)}\n{tt}"},
        "youtube_shorts": {"hook": "", "caption": f"This AI keyboard writes your texts for you. {pick(BRAND['ctas'], d, 4)} {yt}"},
        "reddit":         {"hook": "", "caption": f"{PROD['one_liner']} It's free (50 replies/day), iOS + Android: "
                                      f"{PROD['links']['site']}. Solo dev — would genuinely love feedback on what "
                                      f"would make you keep a keyboard like this installed.",
                           "title": "I built an AI keyboard that reads your chat screenshots and writes the reply — feedback welcome",
                           "subreddit": "sideproject"},
    }


def main():
    load_env()
    d = today()
    outdir = os.path.join(ROOT, "outbox", d)
    os.makedirs(outdir, exist_ok=True)
    caps = captions(d)
    batch = {"date": d, "llm": bool(os.environ.get("REVERT_LLM_KEY")), "items": {}}
    for ch, fn in GENERATORS.items():
        content = fn(d)
        path = os.path.join(outdir, f"{ch}.md")
        with open(path, "w") as fh:
            fh.write(f"# Revert · {ch} · {d}\n\n{content}\n")
        ang = pick_angle(d, ch)
        meta = caps.get(ch, {})
        batch["items"][ch] = {
            "file": f"{ch}.md", "channel": ch,
            "angle": ang["id"], "audience": ang["audience"],
            **meta,
        }
        print(f"  ✓ {ch:14s} -> outbox/{d}/{ch}.md")
    with open(os.path.join(outdir, "batch.json"), "w") as fh:
        json.dump(batch, fh, indent=2)
    print(f"\nBatch ready: marketing/outbox/{d}/  (LLM mode: {'ON' if batch['llm'] else 'template'})")


if __name__ == "__main__":
    main()
