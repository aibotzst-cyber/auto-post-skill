#!/usr/bin/env python3
"""
Tweet Summarizer - Translate and summarize tweets into takeaways.

Supports multiple AI backends:
  - Claude API (Anthropic)
  - OpenAI-compatible APIs
  - Local Ollama

Configure via environment variables:
  SUMMARIZER_BACKEND  = claude | openai | ollama  (default: claude)
  ANTHROPIC_API_KEY   = your Claude API key
  OPENAI_API_KEY      = your OpenAI API key
  OPENAI_BASE_URL     = custom endpoint (for compatible APIs)
  OLLAMA_HOST         = Ollama host (default: http://localhost:11434)
  OLLAMA_MODEL        = Ollama model (default: llama3)
  SUMMARY_LANG        = output language (default: zh-CN)
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional


# --- Configuration ---

BACKEND = os.environ.get("SUMMARIZER_BACKEND", "claude")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
SUMMARY_LANG = os.environ.get("SUMMARY_LANG", "zh-CN")

SYSTEM_PROMPT = """你是一个专业的社交媒体内容分析师，擅长从大佬推文中提炼对他人有用的洞察。

你的任务：
1. 将推文内容翻译成{lang}（如果已是目标语言则跳过翻译）
2. 对每条推文逐一深度解读，提炼 3-5 条 takeaway 洞察
3. 生成一条适合发布到 X/Twitter 的总结推文

核心原则 —— 以「对读者有用」为最高优先级：
- 每条推文必须提炼 3-5 个 takeaway，不是简单复述，而是提炼出可操作的洞察
- Takeaway 要回答：「读者看完能学到什么？能用在哪里？该怎么做？」
- 优先提炼：可操作的建议、反直觉的观点、行业趋势判断、技术选型参考、避坑经验
- 如果是技术内容，保留关键术语并解释其意义
- 每条推文必须附带互动数据（点赞、转发、评论、浏览量）
- 输出 JSON 格式"""

USER_PROMPT_TEMPLATE = """请深度分析以下来自 @{username} 的 Top {tweet_count} 热门推文（按互动量排序）。

要求：对每条推文提炼 3-5 条有价值的 takeaway 洞察，以「对他人有用」为原则。

--- 推文列表（按点赞+转发排序）---
{tweets_text}
--- 结束 ---

请以如下 JSON 格式返回：
{{
  "source_user": "@{username}",
  "tweet_count": {tweet_count},
  "tweet_analyses": [
    {{
      "rank": 1,
      "original_text": "原文摘要（前50字）",
      "tweet_url": "原文链接",
      "takeaways": [
        "洞察1：可操作的建议或反直觉观点",
        "洞察2：行业趋势或技术判断",
        "洞察3：对从业者的启示",
        "洞察4：（可选）延伸思考",
        "洞察5：（可选）相关建议"
      ],
      "stats": {{
        "likes": <点赞数>,
        "retweets": <转发数>,
        "replies": <评论数>,
        "views": <浏览量>
      }}
    }}
  ],
  "summary_tweet": "适合发布的总结推文（不超过 280 字符，涵盖最核心的 1-2 个洞察）",
  "topics": ["话题标签1", "话题标签2"]
}}"""


def _call_claude(system: str, user: str) -> Optional[str]:
    """Call Claude API."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())

    content = data.get("content", [])
    if content:
        return content[0].get("text", "")
    return None


def _call_openai(system: str, user: str) -> Optional[str]:
    """Call OpenAI-compatible API."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 2048,
    }).encode()

    req = urllib.request.Request(
        f"{OPENAI_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())

    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return None


def _call_ollama(system: str, user: str) -> Optional[str]:
    """Call local Ollama API."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())

    return data.get("message", {}).get("content", "")


def _call_llm(system: str, user: str) -> str:
    """Call the configured LLM backend."""
    backends = {
        "claude": _call_claude,
        "openai": _call_openai,
        "ollama": _call_ollama,
    }
    fn = backends.get(BACKEND)
    if not fn:
        raise ValueError(f"Unknown backend: {BACKEND}. Use: claude, openai, ollama")
    result = fn(system, user)
    if not result:
        raise RuntimeError(f"Empty response from {BACKEND}")
    return result


def _build_tweet_url(tw: dict) -> str:
    """Build the original tweet URL from available fields."""
    url = tw.get("url", "")
    if url:
        return url
    tweet_id = tw.get("tweet_id", "")
    author = tw.get("screen_name", "") or tw.get("author", "").lstrip("@")
    if tweet_id and author:
        return f"https://x.com/{author}/status/{tweet_id}"
    return ""


def _format_tweets_text(tweets: list) -> str:
    """Format tweet list into readable text for the prompt."""
    parts = []
    for i, tw in enumerate(tweets, 1):
        text = tw.get("text", "")
        likes = tw.get("likes", 0)
        retweets = tw.get("retweets", 0)
        replies = tw.get("replies_count", tw.get("replies", 0))
        views = tw.get("views", 0)
        created = tw.get("created_at", "")
        tweet_url = _build_tweet_url(tw)
        engagement = likes + retweets
        parts.append(
            f"[#{i}] (engagement score: {engagement})\n"
            f"    {text}\n"
            f"    ❤️ Likes: {likes} | 🔁 RT: {retweets} | 💬 Replies: {replies} | 👁 Views: {views} | {created}\n"
            f"    🔗 {tweet_url}"
        )
    return "\n\n".join(parts)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response that may contain markdown fences."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    import re
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")


def summarize_tweets(username: str, tweets: list) -> dict:
    """Summarize a list of tweets into takeaways.

    Args:
        username: The Twitter username being summarized.
        tweets: List of tweet dicts with at least 'text' field.

    Returns:
        Dict with takeaways, summary_tweet, and topics.
    """
    if not tweets:
        return {
            "source_user": f"@{username}",
            "tweet_count": 0,
            "takeaways": [],
            "summary_tweet": "",
            "topics": [],
            "error": "No tweets to summarize",
        }

    tweets_text = _format_tweets_text(tweets)
    system = SYSTEM_PROMPT.format(lang=SUMMARY_LANG)
    user = USER_PROMPT_TEMPLATE.format(
        username=username,
        tweets_text=tweets_text,
        tweet_count=len(tweets),
    )

    try:
        raw = _call_llm(system, user)
        result = _extract_json(raw)
        return result
    except Exception as e:
        return {
            "source_user": f"@{username}",
            "tweet_count": len(tweets),
            "takeaways": [],
            "summary_tweet": "",
            "topics": [],
            "error": str(e),
        }


def format_post_text(summary: dict) -> str:
    """Format the summary into a tweet-ready text.

    Uses tweet_analyses (with per-tweet stats) if available,
    falls back to takeaways for backward compatibility.
    """
    parts = []
    source = summary.get("source_user", "")
    analyses = summary.get("tweet_analyses", [])
    summary_tweet = summary.get("summary_tweet", "")
    topics = summary.get("topics", [])

    if summary_tweet:
        parts.append(summary_tweet)

    if analyses:
        for a in analyses[:5]:
            rank = a.get("rank", "")
            # Support both new 'takeaways' list and old 'takeaway' string
            takeaways = a.get("takeaways", [])
            if not takeaways:
                single = a.get("takeaway", "")
                if single:
                    takeaways = [single]
            stats = a.get("stats", {})
            likes = stats.get("likes", 0)
            rt = stats.get("retweets", 0)
            replies = stats.get("replies", 0)
            views = stats.get("views", 0)
            tweet_url = a.get("tweet_url", "")
            parts.append(f"\n📌 #{rank}  ❤️{likes} 🔁{rt} 💬{replies} 👁{views}")
            for t in takeaways[:5]:
                parts.append(f"  • {t}")
            if tweet_url:
                parts.append(f"  🔗 {tweet_url}")
    else:
        # Fallback: old flat takeaways format
        takeaways = summary.get("takeaways", [])
        if takeaways:
            parts.append("")
            for i, t in enumerate(takeaways[:5], 1):
                parts.append(f"  {i}. {t}")

    if source:
        parts.append(f"\nvia {source}")

    if topics:
        parts.append(" ".join(f"#{t}" for t in topics[:3]))

    return "\n".join(parts)


if __name__ == "__main__":
    # Test with sample data
    test_tweets = [
        {
            "text": "Just released our new AI model. It achieves state-of-the-art on 15 benchmarks.",
            "likes": 5000,
            "retweets": 2000,
            "views": 500000,
            "created_at": "2026-03-20",
        },
        {
            "text": "Thread on how we built it: 1/ We started with a novel architecture...",
            "likes": 3000,
            "retweets": 1500,
            "views": 300000,
            "created_at": "2026-03-20",
        },
    ]
    result = summarize_tweets("testuser", test_tweets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
