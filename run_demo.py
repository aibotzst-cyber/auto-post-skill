#!/usr/bin/env python3
"""
Demo run: end-to-end pipeline with real tweet data.

Since FxTwitter API is blocked by network policy in this environment,
we inject real tweet data fetched via web search, then run the full
summarize → format → (dry-run) post pipeline.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from auto_post import rank_tweets, filter_yesterday_tweets, run_pipeline, load_config
from summarizer import summarize_tweets, format_post_text, _build_tweet_url

# ---------------------------------------------------------------------------
# Real tweet data (from web search, March 2026)
# ---------------------------------------------------------------------------

yesterday = (datetime.now(timezone.utc) - timedelta(days=1))
ts = yesterday.strftime("%a %b %d %H:%M:%S %z %Y")

REAL_TWEETS = {
    "karpathy": [
        {
            "text": "I've never felt this much behind as a programmer. The profession is being dramatically refactored as the bits contributed by the programmer are increasingly sparse and between. I have a sense that I could be 10X more powerful if I just properly string together what has become available.",
            "screen_name": "karpathy",
            "tweet_id": "2004607146781278521",
            "likes": 45200,
            "retweets": 8900,
            "replies_count": 3200,
            "views": 12500000,
            "created_at": ts,
        },
        {
            "text": "Three days ago I left autoresearch tuning nanochat for ~2 days on depth=12 model. It found ~20 changes that improved the validation loss. I tested these changes yesterday and all of them were additive and transferred to larger (depth=24) models. Stacking up all of these changes, the result is a significant improvement.",
            "screen_name": "karpathy",
            "tweet_id": "2031135152349524125",
            "likes": 28700,
            "retweets": 5400,
            "replies_count": 1800,
            "views": 8200000,
            "created_at": ts,
        },
        {
            "text": "I packaged up the 'autoresearch' project into a new self-contained minimal repo. It's basically nanochat LLM training core stripped down to a single-GPU, one file version of ~630 lines of code, then: the human iterates on the prompt (.md) and the AI agent iterates on the training code (.py). The agent works in an autonomous loop on a git feature branch.",
            "screen_name": "karpathy",
            "tweet_id": "2030371219518931079",
            "likes": 32100,
            "retweets": 7200,
            "replies_count": 2100,
            "views": 9800000,
            "created_at": ts,
        },
        {
            "text": "A few random notes from claude coding quite a bit last few weeks. Given the latest lift in LLM coding capability, like many others I rapidly went from about 80% manual+autocomplete coding and 20% agents in November to 80% agent coding and 20% edits+touchups.",
            "screen_name": "karpathy",
            "tweet_id": "2015883857489522876",
            "likes": 38500,
            "retweets": 6800,
            "replies_count": 2900,
            "views": 11200000,
            "created_at": ts,
        },
        {
            "text": "karpathy/jobs — I scraped every job in the US economy (342 occupations from BLS) and scored each one's AI exposure 0-10 using an LLM. Out of 143 million working people in the US, approximately 57 million are at high to very high risk of their jobs being negatively impacted by AI — almost 40%.",
            "screen_name": "karpathy",
            "tweet_id": "2033236945539588524",
            "likes": 52000,
            "retweets": 14200,
            "replies_count": 5600,
            "views": 18900000,
            "created_at": ts,
        },
        {
            "text": "Good morning everyone, hope you have a great day!",
            "screen_name": "karpathy",
            "tweet_id": "2033000000000000000",
            "likes": 8900,
            "retweets": 200,
            "replies_count": 1500,
            "views": 2100000,
            "created_at": ts,
        },
        {
            "text": "I'm being accused of overhyping. People's reactions varied very widely, from 'how is this interesting at all' all the way to 'it's so over'. To add a few words beyond just memes in jest...",
            "screen_name": "karpathy",
            "tweet_id": "2017442712388309406",
            "likes": 15200,
            "retweets": 2100,
            "replies_count": 980,
            "views": 5400000,
            "created_at": ts,
        },
    ],
    "sama": [
        {
            "text": "I have so much gratitude to people who wrote extremely complex software character-by-character. It already feels difficult to remember how much effort it really took. Thank you for getting us to this point.",
            "screen_name": "sama",
            "tweet_id": "2019500000000000001",
            "likes": 89000,
            "retweets": 12500,
            "replies_count": 15200,
            "views": 45000000,
            "created_at": ts,
        },
        {
            "text": "We love working with NVIDIA and they make the best AI chips in the world. We hope to be a gigantic customer for a very long time. I don't get where all this insanity is coming from.",
            "screen_name": "sama",
            "tweet_id": "2018451015272694248",
            "likes": 35200,
            "retweets": 4800,
            "replies_count": 6700,
            "views": 22000000,
            "created_at": ts,
        },
        {
            "text": "One thing I think I did wrong: we shouldn't have rushed to get the Pentagon deal out on Friday. The issues are super complex, and demand clear communication. We were genuinely trying to de-escalate things and avoid a much worse outcome, but I think it just looked opportunistic and sloppy.",
            "screen_name": "sama",
            "tweet_id": "2018000000000000001",
            "likes": 42000,
            "retweets": 8900,
            "replies_count": 9200,
            "views": 31000000,
            "created_at": ts,
        },
        {
            "text": "We have set internal goals of having an automated AI research intern by September of 2026 running on hundreds of thousands of GPUs, and a true automated AI researcher by March of 2028. We may totally fail at this goal.",
            "screen_name": "sama",
            "tweet_id": "1983584366547829073",
            "likes": 67000,
            "retweets": 18200,
            "replies_count": 8900,
            "views": 38000000,
            "created_at": ts,
        },
    ],
}


def monkey_patch_fetch():
    """Replace fetch_user_timeline with our real data injection."""
    import auto_post

    original_fetch = auto_post.fetch_user_yesterday_tweets

    def patched_fetch(username, limit=50, camofox_port=9377, **kwargs):
        if username in REAL_TWEETS:
            tweets = REAL_TWEETS[username]
            print(f"\n[demo] Injecting {len(tweets)} real tweets for @{username}")
            yesterday_tweets = filter_yesterday_tweets(tweets)
            print(f"[demo] {len(yesterday_tweets)} tweets from yesterday")
            top_n = kwargs.get("top_n", 5)
            ranked = rank_tweets(yesterday_tweets, top_n=top_n)
            print(f"[demo] Top {len(ranked)} by engagement:")
            for i, tw in enumerate(ranked, 1):
                score = tw["likes"] + tw["retweets"]
                print(f"  #{i} score={score:,} | {tw['text'][:60]}...")
            return ranked
        return original_fetch(username, limit, camofox_port, **kwargs)

    auto_post.fetch_user_yesterday_tweets = patched_fetch


if __name__ == "__main__":
    monkey_patch_fetch()

    config = load_config("auto_post_config.json")
    # Only run for users we have data for
    config["source_users"] = ["karpathy", "sama"]
    config["dry_run"] = True
    config["top_n"] = 5

    print("=" * 70)
    print("  AUTO POST SKILL — LIVE DEMO RUN")
    print("=" * 70)
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Users: {config['source_users']}")
    print(f"  Top N: {config['top_n']}")
    print(f"  Mode: DRY RUN")
    print("=" * 70)

    results = run_pipeline(config)

    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    for r in results:
        print(f"\n{'─' * 70}")
        print(f"  @{r['username']} — {r['tweet_count']} tweets — {r['status']}")
        print(f"{'─' * 70}")
        if r.get("post_text"):
            print(r["post_text"])
        if r.get("summary") and r["summary"].get("error"):
            print(f"  Error: {r['summary']['error']}")
