#!/usr/bin/env python3
"""
Auto Post - Fetch yesterday's tweets, summarize, and post to X.

Workflow:
  1. Fetch yesterday's tweets from specified X/Twitter users (via x-tweet-fetcher)
  2. Translate & summarize into takeaways (via AI)
  3. Post summary tweets to your X account (via Chrome CDP)

Usage:
  python3 auto_post.py --config auto_post_config.json
  python3 auto_post.py --users elonmusk,kaboratoss --dry-run
  python3 auto_post.py --users elonmusk --post

Environment variables:
  See summarizer.py for AI backend config.
  CHROME_CDP_PORT  = Chrome DevTools port (default: 9222)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

# Add scripts/ to path for x-tweet-fetcher imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from scripts.fetch_tweet import fetch_tweet, fetch_user_timeline
from summarizer import summarize_tweets, format_post_text
from cdp_poster import post_tweet, check_chrome_cdp


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "source_users": [],           # X usernames to fetch from
    "post_account": "",           # (informational) which account to post to
    "chrome_cdp_port": 9222,
    "camofox_port": 9377,
    "fetch_limit": 50,            # max tweets per user
    "top_n": 5,                   # top N tweets by engagement per user
    "summary_lang": "zh-CN",
    "dry_run": False,
    "output_dir": "./output",
}


def load_config(config_path: str = None) -> dict:
    """Load configuration from JSON file or return defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            user_cfg = json.load(f)
        cfg.update(user_cfg)
    return cfg


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------

def is_yesterday(created_at: str) -> bool:
    """Check if a tweet's created_at is from yesterday (UTC)."""
    now_utc = datetime.now(timezone.utc)
    yesterday = (now_utc - timedelta(days=1)).date()

    # FxTwitter format: "Mon Jan 01 12:00:00 +0000 2026"
    for fmt in [
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(created_at, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.date() == yesterday
        except ValueError:
            continue
    return False


def filter_yesterday_tweets(tweets: list) -> list:
    """Filter tweets to only those from yesterday."""
    return [tw for tw in tweets if is_yesterday(tw.get("created_at", ""))]


def rank_tweets(tweets: list, top_n: int = 5) -> list:
    """Sort tweets by engagement (likes + retweets) and return top N."""
    scored = sorted(
        tweets,
        key=lambda tw: tw.get("likes", 0) + tw.get("retweets", 0),
        reverse=True,
    )
    return scored[:top_n]


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def fetch_user_yesterday_tweets(
    username: str,
    limit: int = 50,
    camofox_port: int = 9377,
    **kwargs,
) -> List[Dict]:
    """Fetch a user's tweets from yesterday, ranked by engagement.

    Strategy:
      1. Fetch timeline via Camofox + Nitter
      2. Filter to yesterday's tweets only
      3. Sort by likes + retweets, return top N
    """
    print(f"\n[auto_post] Fetching tweets from @{username}...")

    result = fetch_user_timeline(
        username=username,
        limit=limit,
        camofox_port=camofox_port,
    )

    if "error" in result:
        print(f"[auto_post] Error fetching @{username}: {result['error']}")
        return []

    all_tweets = result.get("tweets", [])
    print(f"[auto_post] Fetched {len(all_tweets)} total tweets from @{username}")

    # Filter to yesterday
    yesterday_tweets = filter_yesterday_tweets(all_tweets)
    print(f"[auto_post] {len(yesterday_tweets)} tweets from yesterday")

    # Rank by engagement and take top N
    top_n = kwargs.get("top_n", 5)
    if yesterday_tweets:
        ranked = rank_tweets(yesterday_tweets, top_n=top_n)
        print(f"[auto_post] Top {len(ranked)} by engagement (likes+RT):")
        for i, tw in enumerate(ranked, 1):
            likes = tw.get("likes", 0)
            rt = tw.get("retweets", 0)
            replies = tw.get("replies_count", 0)
            views = tw.get("views", 0)
            print(f"  #{i} ❤️{likes} 🔁{rt} 💬{replies} 👁{views} | {tw.get('text', '')[:60]}...")
        return ranked

    return yesterday_tweets


def process_user(username: str, config: dict) -> Dict[str, Any]:
    """Full pipeline for one user: fetch -> summarize -> format."""
    tweets = fetch_user_yesterday_tweets(
        username=username,
        limit=config.get("fetch_limit", 50),
        camofox_port=config.get("camofox_port", 9377),
        top_n=config.get("top_n", 5),
    )

    if not tweets:
        return {
            "username": username,
            "tweet_count": 0,
            "summary": None,
            "post_text": None,
            "status": "no_tweets",
        }

    # Summarize
    print(f"[auto_post] Summarizing {len(tweets)} tweets from @{username}...")
    summary = summarize_tweets(username, tweets)

    if summary.get("error"):
        return {
            "username": username,
            "tweet_count": len(tweets),
            "summary": summary,
            "post_text": None,
            "status": f"summarize_error: {summary['error']}",
        }

    # Format for posting
    post_text = format_post_text(summary)

    return {
        "username": username,
        "tweet_count": len(tweets),
        "summary": summary,
        "post_text": post_text,
        "status": "ready",
    }


def run_pipeline(config: dict) -> List[Dict]:
    """Run the full pipeline for all configured users."""
    users = config.get("source_users", [])
    if not users:
        print("[auto_post] No source users configured.")
        return []

    dry_run = config.get("dry_run", False)
    cdp_port = config.get("chrome_cdp_port", 9222)
    output_dir = config.get("output_dir", "./output")

    # Ensure output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Check Chrome CDP if not dry run
    if not dry_run:
        if not check_chrome_cdp(cdp_port):
            print(f"[auto_post] WARNING: Chrome CDP not reachable on port {cdp_port}")
            print("[auto_post] Switching to dry-run mode.")
            dry_run = True

    results = []
    for username in users:
        username = username.strip().lstrip("@")
        result = process_user(username, config)
        results.append(result)

        if result["status"] == "ready" and result["post_text"]:
            print(f"\n{'='*60}")
            print(f"[auto_post] Summary for @{username}:")
            print(f"{'='*60}")
            print(result["post_text"])
            print(f"{'='*60}\n")

            if not dry_run:
                print(f"[auto_post] Posting tweet for @{username}...")
                post_result = post_tweet(result["post_text"], cdp_port)
                result["post_result"] = post_result
                if post_result["success"]:
                    print(f"[auto_post] Posted successfully!")
                    result["status"] = "posted"
                else:
                    print(f"[auto_post] Post failed: {post_result['message']}")
                    result["status"] = f"post_failed: {post_result['message']}"
                time.sleep(10)  # Wait between posts to avoid rate limits
            else:
                print("[auto_post] (dry-run mode, not posting)")
                result["status"] = "dry_run"

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"auto_post_{timestamp}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[auto_post] Results saved to {output_file}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Auto-fetch, summarize, and post tweets from X/Twitter."
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config JSON file",
    )
    parser.add_argument(
        "--users", "-u",
        help="Comma-separated list of X usernames to fetch",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Don't actually post, just show what would be posted",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Actually post tweets (default is dry-run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max tweets to fetch per user (default: 50)",
    )
    parser.add_argument(
        "--cdp-port",
        type=int,
        default=9222,
        help="Chrome CDP port (default: 9222)",
    )
    parser.add_argument(
        "--camofox-port",
        type=int,
        default=9377,
        help="Camofox port (default: 9377)",
    )
    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="Output directory (default: ./output)",
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # CLI overrides
    if args.users:
        config["source_users"] = [u.strip() for u in args.users.split(",")]
    if args.dry_run or not args.post:
        config["dry_run"] = True
    if args.post:
        config["dry_run"] = False
    config["fetch_limit"] = args.limit
    config["chrome_cdp_port"] = args.cdp_port
    config["camofox_port"] = args.camofox_port
    config["output_dir"] = args.output

    # Run
    print("[auto_post] Starting pipeline...")
    print(f"[auto_post] Users: {config['source_users']}")
    print(f"[auto_post] Mode: {'DRY RUN' if config['dry_run'] else 'LIVE POST'}")
    print(f"[auto_post] Fetch limit: {config['fetch_limit']} tweets/user")
    print()

    results = run_pipeline(config)

    # Summary
    print("\n" + "=" * 60)
    print("[auto_post] Pipeline complete!")
    for r in results:
        status = r["status"]
        count = r["tweet_count"]
        user = r["username"]
        print(f"  @{user}: {count} tweets -> {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
