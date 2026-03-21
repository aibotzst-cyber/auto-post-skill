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

SYSTEM_PROMPT = """你是一个专业的社交媒体内容分析师。你的任务是：
1. 将推文内容翻译成{lang}（如果已是目标语言则跳过翻译）
2. 提炼出核心 takeaway（关键要点）
3. 生成一条适合发布到 X/Twitter 的总结推文

要求：
- Takeaway 要简洁有力，抓住核心观点
- 总结推文不超过 280 字符
- 如果是技术内容，保留关键术语
- 输出 JSON 格式"""

USER_PROMPT_TEMPLATE = """请分析以下来自 @{username} 的推文内容，提炼 takeaway 并生成总结推文。

--- 推文列表 ---
{tweets_text}
--- 结束 ---

请以如下 JSON 格式返回：
{{
  "source_user": "@{username}",
  "tweet_count": <分析的推文数量>,
  "takeaways": [
    "要点1",
    "要点2",
    ...
  ],
  "summary_tweet": "适合发布的总结推文（不超过 280 字符）",
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


def _format_tweets_text(tweets: list) -> str:
    """Format tweet list into readable text for the prompt."""
    parts = []
    for i, tw in enumerate(tweets, 1):
        text = tw.get("text", "")
        likes = tw.get("likes", 0)
        retweets = tw.get("retweets", 0)
        views = tw.get("views", 0)
        created = tw.get("created_at", "")
        parts.append(
            f"[{i}] {text}\n"
            f"    Likes: {likes} | RT: {retweets} | Views: {views} | {created}"
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
    user = USER_PROMPT_TEMPLATE.format(username=username, tweets_text=tweets_text)

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

    Combines takeaways and the summary tweet into a publishable format.
    """
    parts = []
    source = summary.get("source_user", "")
    takeaways = summary.get("takeaways", [])
    summary_tweet = summary.get("summary_tweet", "")
    topics = summary.get("topics", [])

    if summary_tweet:
        parts.append(summary_tweet)

    if takeaways:
        parts.append("")
        parts.append("Key takeaways:")
        for i, t in enumerate(takeaways[:3], 1):
            parts.append(f"  {i}. {t}")

    if source:
        parts.append(f"\nvia {source}")

    if topics:
        parts.append(" ".join(f"#{t}" for t in topics[:3]))

    text = "\n".join(parts)

    # Trim to 280 chars if needed (Twitter limit)
    if len(text) > 280:
        text = text[:277] + "..."

    return text


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
