# Revert — Autonomous Marketing Engine

A self-running content + posting system for Revert across **every channel**:
TikTok · Instagram · YouTube Shorts · X · Reddit · Email · Blog/SEO · App Store/Play ASO.

It is built to run **hands-off on a daily cron**. It degrades gracefully — it does
something useful with zero credentials, and unlocks more autonomy as you add keys.

```
brand.json   ← single source of truth: positioning, voice, angles, hooks, channel specs
engine.py    ← generates a fresh content batch for all channels (LLM-backed; template fallback)
post.py      ← publishes the batch (one aggregator key → all channels; dry-run by default)
run.sh       ← the daily loop cron calls: generate → post → log
outbox/<date>/  ← the generated, ready-to-post content + QUEUE.md + batch.json
secrets.example.env → copy to .env to unlock AI copy + auto-posting
```

## Run it now (no keys needed)

```bash
cd marketing
./run.sh
```

Produces `outbox/<today>/` with a post for every channel and a `QUEUE.md` you can
copy/paste. That's the **Tier 1** baseline — it works today, this minute.

## The three tiers of autonomy

| Tier | Add this | You get |
|------|----------|---------|
| **1. Baseline** | nothing | Daily content composed from the brand hook/angle library, varied by date, written to `outbox/` + `QUEUE.md`. You copy/paste to post. |
| **2. Fresh AI copy** | `REVERT_LLM_KEY` in `.env` | Every run writes net-new, AI-generated copy per channel instead of library templates. Cheapest path points at your own `api.gorevert.com` proxy. |
| **3. Full auto-post** | a posting-provider key + `REVERT_POST_LIVE=1` | The batch is **published automatically** to X, Instagram, Reddit, etc. Truly hands-off. **See [SETUP.md](SETUP.md).** |

### Why an aggregator instead of 6 OAuth apps
"Auto-post to all channels" normally means registering a developer app on X, Meta,
TikTok, Google, Reddit — each with its own review, audit, and breakage (TikTok literally
won't allow public auto-posts without passing an audit). An aggregator collapses that to
**one key** and inherits the audited/approved access for the hard platforms. `post.py`
supports two, picked with `REVERT_POST_PROVIDER`:
- **`upload_post`** (default, recommended) — one key, **direct file upload** (no media
  hosting), free to start then ~$16/mo. Set `UPLOAD_POST_KEY` + `UPLOAD_POST_USER`.
- **`ayrshare`** — most mature, **$149/mo** (no free tier as of 2026), needs media at a
  public URL (`REVERT_MEDIA_BASE`, e.g. Cloudflare R2).

Full verified walkthrough + the real per-platform gotchas: **[SETUP.md](SETUP.md)**.

## Visual content (images + video)

Image/video channels are marked `needs media` until an asset exists.

### Images — Nano Banana (Gemini), already wired
- `genimage.py "<prompt>" out.png [9:16|4:5|1:1|16:9]` — one image.
- `campaign.py` — generates the whole standard set (hero, before/after, square ad,
  short-form hook frame, blog hero) into `outbox/<date>/img/` in one command.
- Uses `REVERT_IMAGE_KEY` from `.env`. **Status: key is valid but its AI Studio project
  is on prepay billing at $0 — every call 429s.** Top up at https://ai.studio/projects
  and both `genimage.py` and `campaign.py` work immediately, no code changes.
- The SAME key also powers the daily AI copy (Tier 2) via Gemini's OpenAI-compatible
  endpoint — already wired in `.env`. Funding the project lights up copy + images together.

### Video (TikTok / Reels / Shorts)
1. **Higgsfield (AI)** — each `tiktok.md` includes a ready `HIGGSFIELD VIDEO PROMPT`
   (needs Higgsfield credits — currently 0).
2. **Real screen recordings** — a 10s capture of the keyboard usually beats AI b-roll for
   a UI product. Record once, reuse across all three short-form channels.

## Going fully autonomous — checklist

- [ ] `cp secrets.example.env .env`
- [ ] (Optional) Add `REVERT_LLM_KEY` for fresh AI copy → Tier 2
- [ ] Create an Upload-Post account, connect Revert's socials, add `UPLOAD_POST_KEY` + `UPLOAD_POST_USER` → Tier 3 (full steps in [SETUP.md](SETUP.md))
- [ ] Set `REVERT_POST_LIVE=1` (start with one channel to test)
- [ ] Confirm the daily cron is installed (`crontab -l | grep run.sh`)
- [ ] (Optional) Record a 10s keyboard clip to unlock TikTok/Reels/Shorts

Until those are done the system still runs daily and stockpiles ready-to-post content.

## Editing the strategy
Everything the engine says comes from `brand.json` — edit angles, hooks, CTAs, hashtags,
cadence there and every channel updates. No code changes needed for messaging.

## Schedule
Installed via cron to run `run.sh` once daily. See `calendar.md` for the weekly cadence
and posting-time guidance per channel.
