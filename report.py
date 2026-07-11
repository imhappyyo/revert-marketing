#!/usr/bin/env python3
"""
Revert marketing performance report.

Reads marketing/performance.csv (written by post.py) and summarizes which brand
angles / audiences are performing best. Works at every data tier:
  - file missing / header only -> tells you to run the engine + post first.
  - all metric columns empty    -> shows POST COUNTS + angle/audience coverage.
  - some metrics filled         -> ranks angles & audiences by the chosen metric
                                   (and per-post averages), ignoring blank cells.

Usage:
  python3 report.py                 # auto-pick a metric (installs>clicks>likes>views), else coverage
  python3 report.py --metric likes  # force a metric
  python3 report.py --csv PATH      # alternate csv path

Stdlib only.
"""
import os, sys, csv, argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(ROOT, "performance.csv")
METRICS = ["installs", "clicks", "likes", "views"]  # preference order for auto-pick


def load(path):
    if not os.path.exists(path):
        return None, []
    with open(path, newline="") as fh:
        r = csv.DictReader(fh)
        rows = list(r)
        return r.fieldnames, rows


def to_num(s):
    s = (s or "").strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def filled_metrics(rows):
    """Which metric columns have at least one numeric value."""
    out = []
    for m in METRICS:
        if any(to_num(row.get(m)) is not None for row in rows):
            out.append(m)
    return out


def bar(n, peak, width=24):
    if peak <= 0:
        return ""
    return "█" * max(1, int(round(width * n / peak)))


def print_coverage(rows):
    print("No metrics filled in yet — showing coverage (posts logged).\n")
    print(f"Total posts logged: {len(rows)}")
    dates = sorted({r.get('date', '') for r in rows})
    chans = sorted({r.get('channel', '') for r in rows})
    print(f"Dates: {len(dates)} ({dates[0]}..{dates[-1]})  Channels: {', '.join(chans)}\n")
    for dim in ("angle", "audience"):
        counts = defaultdict(int)
        for r in rows:
            counts[r.get(dim) or "(none)"] += 1
        peak = max(counts.values()) if counts else 0
        print(f"Posts per {dim}:")
        for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {k:22s} {v:3d}  {bar(v, peak)}")
        print()
    print("Fill in views/likes/clicks/installs in performance.csv, then re-run for rankings.")


def aggregate(rows, dim, metric):
    total = defaultdict(float)
    n = defaultdict(int)        # rows with a numeric metric value
    posts = defaultdict(int)    # all rows for this dim value
    for r in rows:
        key = r.get(dim) or "(none)"
        posts[key] += 1
        v = to_num(r.get(metric))
        if v is not None:
            total[key] += v
            n[key] += 1
    return total, n, posts


def print_ranking(rows, dim, metric):
    total, n, posts = aggregate(rows, dim, metric)
    if not total:
        return
    peak = max(total.values())
    print(f"Best {dim}s by total {metric}:")
    ordered = sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))
    for k, tot in ordered:
        avg = tot / n[k] if n[k] else 0.0
        print(f"  {k:22s} {metric}={tot:10.0f}  avg/post={avg:8.1f}  "
              f"(n={n[k]}/{posts[k]})  {bar(tot, peak)}")
    print()


def main():
    ap = argparse.ArgumentParser(description="Revert marketing performance report")
    ap.add_argument("--metric", choices=METRICS, help="metric to rank by")
    ap.add_argument("--csv", default=DEFAULT_CSV, help="path to performance.csv")
    args = ap.parse_args()

    fields, rows = load(args.csv)
    if fields is None:
        print(f"No performance.csv at {args.csv}.\nRun engine.py + post.py first "
              f"to start logging posts.")
        return
    if not rows:
        print("performance.csv has a header but no rows yet. Post a batch first.")
        return

    print(f"Revert performance report  —  {len(rows)} posts logged from {args.csv}\n")

    avail = filled_metrics(rows)
    if not avail:
        print_coverage(rows)
        return

    if args.metric and args.metric in avail:
        metric = args.metric
    elif args.metric:
        fallback = next(m for m in METRICS if m in avail)
        print(f"(no data for '{args.metric}' yet; using '{fallback}')\n")
        metric = fallback
    else:
        metric = next(m for m in METRICS if m in avail)

    print(f"Ranking by: {metric}   (filled metrics: {', '.join(avail)})\n")
    print_ranking(rows, "angle", metric)
    print_ranking(rows, "audience", metric)

    # quick channel rollup for the chosen metric
    print_ranking(rows, "channel", metric)


if __name__ == "__main__":
    main()
