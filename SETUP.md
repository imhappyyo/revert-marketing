# Revert auto-posting — what to do (verified June 2026)

The code is done. To turn on hands-off publishing you do three things: **pick a poster,
connect your accounts, paste one key.** Then the daily cron posts for you.

> Honest finding from the research pass: there is **no free, zero-setup way** to fully
> auto-post to all 7 networks. Every route has a gate (a fee, an app review, or an audit).
> Below is the cheapest route that actually works, and exactly where the real walls are.

---

## Recommended path: Upload-Post + free images  (~$0–16/mo)

**Why:** one API key for all channels, it takes **direct file uploads** (so no media
hosting to set up), and it has a free tier to start. Our `creative.py` already makes the
images for free, so your only possible cost is Upload-Post itself.

### Do this (10 minutes)
1. Go to **https://upload-post.com** → create an account.
2. Create a **profile** (e.g. name it `revert`) and **connect Revert's social accounts**
   to it (Instagram, X, Reddit, Facebook, LinkedIn — TikTok/YouTube when you have video).
   Each network is a one-time OAuth "Connect" click.
3. Copy your **API key** from the dashboard.
4. In `marketing/.env` set:
   ```
   REVERT_POST_PROVIDER=upload_post
   UPLOAD_POST_KEY=<your key>
   UPLOAD_POST_USER=revert        # the profile name from step 2
   REVERT_POST_LIVE=1
   ```
5. Test one post without waiting for cron:
   ```
   cd marketing && python3 engine.py && python3 creative.py && python3 post.py
   ```
   Watch for `✓ POSTED`. The 9am cron then runs it daily on its own.

Free tier ≈ 10 uploads/month (one cross-post can use several), so once you're posting
daily, upgrade to **Basic ~$16/mo (unlimited)**. Still the cheapest one-integration route.

---

## Alternative: Ayrshare (most mature, **$149/mo**, no free tier)
Only worth it if you outgrow Upload-Post. It needs media at a **public URL**, so you also
host the images on **Cloudflare R2** (free — you already have gorevert.com on Cloudflare):

1. Cloudflare → R2 → create bucket `revert-media` → Settings → add custom domain
   `media.gorevert.com` (or use the one-click `r2.dev` URL to start).
2. R2 → API tokens → create one → `brew install rclone`, configure an `r2` remote.
3. Have the daily run upload the day's images: `rclone copy outbox/<date>/img r2:revert-media/<date>/img`
4. In `.env`: `REVERT_POST_PROVIDER=ayrshare`, `AYRSHARE_KEY=...`,
   `REVERT_MEDIA_BASE=https://media.gorevert.com`, `REVERT_POST_LIVE=1`.

---

## The real walls (true for ANY tool — plan around these)

| Channel | Status | What it means for you |
|--------|--------|------------------------|
| **X / Twitter** | ⚠️ Pay-per-post | X has no free API tier (2026); ~$0.01/post. Aggregators on paid plans cover this. Note: links are stripped from the post body (we put the link in the first comment). |
| **Instagram** | ✅ works, gated | Needs a **Professional (Business/Creator)** account + linked Facebook Page. The aggregator handles the API review; you just connect the account. Feed/Reels/carousels OK. Max 100 posts/24h. |
| **Facebook** | ✅ works | Connect the Page. Same Meta gating, handled by the aggregator. |
| **LinkedIn** | ✅ personal / ⚠️ company | Personal profile posting is fine. Company-Page posting is partner-gated (the aggregator's access covers it). |
| **YouTube** | ✅ easy | Connect channel once. (Needs a video — see below.) |
| **TikTok** | ⛔ audit wall | Public auto-posting requires **audited** API access. This is exactly why we use an aggregator — you inherit *their* audited access. Without it, posts are private-only. (Also needs a video.) |
| **Reddit** | ⚠️ approval + mods | API access needs manual approval (since Nov 2025) and **mods/automod remove bot self-promo**. Use it sparingly and authentically, not for daily blasting. Posts to `r/sideproject` by default. |

## Video (TikTok / Reels / Shorts)
The engine writes the script + shot list; it can't film. Until you add a clip these channels
stay queued. Fastest win: a **10-second screen recording** of the keyboard → drop it in
`outbox/<date>/img/` and extend `post.py` to send it as `video`. (Higgsfield AI video is the
other option but its credits are at $0.)

## Safety
`REVERT_POST_LIVE=0` (default) = dry-run; everything goes to `outbox/<date>/QUEUE.md` to
copy/paste. Flip to `1` only when you've connected accounts and want it truly hands-off.
Start with one channel (e.g. just `x` or `instagram`) before enabling all of them.
