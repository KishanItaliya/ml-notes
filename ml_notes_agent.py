"""
ML Notes Agent
==============
Watches a YouTube video link → extracts transcript → summarizes with AI →
does real-world research → generates .md notes + .py code examples →
pushes everything to your GitHub repo.

100% FREE to run:
  - youtube-transcript-api  (no key needed)
  - Groq free tier          (get key at console.groq.com)
  - DuckDuckGo HTML scrape  (no key needed)
  - GitHub REST API         (free with your token)

Usage:
  python ml_notes_agent.py "https://www.youtube.com/watch?v=VIDEO_ID"
"""

import os
import sys
import json
import re
import time
import base64
import textwrap
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs

import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# Load .env file from the same directory as this script
# ─────────────────────────────────────────────
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    print(f"[WARNING] No .env file found at {_env_path}")
    print("          Copy .env.example to .env and fill in your keys.")

# ─────────────────────────────────────────────
# CONFIG  (loaded from .env or system env vars)
# ─────────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "YOUR_GITHUB_TOKEN_HERE")
GITHUB_REPO     = os.getenv("GITHUB_REPO",  "your-username/ml-notes")   # e.g. "john/ml-study"
NOTES_FOLDER    = os.getenv("NOTES_FOLDER", "notes")                    # folder inside repo
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
DDG_SEARCH_URL  = "https://html.duckduckgo.com/html/"
MAX_TRANSCRIPT_CHARS = 12000   # keep within Groq context window
MAX_RESEARCH_RESULTS = 4       # number of DDG snippets to include
# ─────────────────────────────────────────────


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
    raise ValueError(f"Cannot extract video ID from: {url}")


def get_video_metadata(video_id: str) -> dict:
    """Fetch basic video info (title, channel) from YouTube oEmbed – no API key needed."""
    url = f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return {
            "title":   data.get("title", "Unknown Title"),
            "channel": data.get("author_name", "Unknown Channel"),
        }
    except Exception:
        return {"title": "Unknown Title", "channel": "Unknown Channel"}


def get_transcript(video_id: str) -> str:
    """Fetch and join the transcript for a YouTube video."""
    print("  [1/5] Fetching transcript ...")
    try:
        # New API for version 1.x
        # Try Hindi and English variants first
        languages = ['hi', 'en', 'en-IN', 'en-US', 'en-GB']
        
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=languages)
        
        text = " ".join(chunk.text for chunk in transcript)
        # Trim to context budget
        if len(text) > MAX_TRANSCRIPT_CHARS:
            text = text[:MAX_TRANSCRIPT_CHARS] + "\n[... transcript truncated ...]"
        return text
    except Exception as e:
        print(f"    [ERROR] Failed to fetch transcript: {e}")
        print("    Common causes:")
        print("      - Video has no captions/subtitles")
        print("      - Transcripts are disabled by the uploader")
        print("      - Video is private or restricted")
        raise


def groq_chat(messages: list, max_tokens: int = 2048, temperature: float = 0.4) -> str:
    """Call the Groq chat completions endpoint."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       GROQ_MODEL,
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
    }
    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def summarize_transcript(transcript: str, meta: dict) -> dict:
    """
    Ask Groq to produce a structured summary from the transcript.
    Returns a dict with keys: topic, summary, key_concepts, prerequisites,
    needs_code (bool), code_topics (list).
    """
    print("  [2/5] Summarizing with AI ...")
    system = textwrap.dedent("""
        You are an expert ML educator. A student gave you a YouTube lecture transcript.
        Return ONLY a JSON object (no markdown fences) with these exact keys:
        {
          "topic": "<concise topic name, e.g. 'Gradient Descent'>",
          "summary": "<2–3 sentence plain-English summary>",
          "key_concepts": ["concept1", "concept2", ...],
          "prerequisites": ["item1", "item2", ...],
          "needs_code": true or false,
          "code_topics": ["topic1", ...]
        }
        needs_code = true if the lecture covers algorithms, data structures, or
        anything that benefits from a runnable Python example.
    """).strip()

    user = (
        f"Video title: {meta['title']}\n"
        f"Channel: {meta['channel']}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )

    raw = groq_chat([
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], max_tokens=512, temperature=0.2)

    # Strip accidental markdown fences just in case
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def research_topic(topic: str, key_concepts: list) -> str:
    """
    Scrape DuckDuckGo HTML for production/industry context.
    Returns a plain-text blob of combined snippets.
    """
    print("  [3/5] Researching industry usage ...")
    queries = [
        f"{topic} machine learning production best practices",
        f"{topic} real world use cases industry 2024",
    ]
    snippets = []

    for query in queries:
        try:
            r = requests.post(
                DDG_SEARCH_URL,
                data={"q": query, "b": ""},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            soup = BeautifulSoup(r.text, "html.parser")
            results = soup.select(".result__snippet")[:MAX_RESEARCH_RESULTS]
            for res in results:
                text = res.get_text(" ", strip=True)
                if len(text) > 40:
                    snippets.append(text)
            time.sleep(1)          # be polite to DDG
        except Exception as e:
            print(f"    [!] DDG search failed for '{query}': {e}")

    return "\n\n".join(snippets) if snippets else "No research results found."


def generate_notes(meta: dict, info: dict, research: str) -> str:
    """Ask Groq to write the full .md notes file."""
    print("  [4a/5] Generating Markdown notes ...")
    date_str = datetime.now().strftime("%Y-%m-%d")

    system = textwrap.dedent("""
        You are a senior ML engineer writing study notes for a front-end developer
        learning ML from YouTube. Your notes must:
        - Use clear headings (##, ###)
        - Explain every concept in simple English first, then go deeper
        - Include a "Real-World Usage" section with current industry examples
        - Include a "Best Practices" section with production tips
        - Use tables, bullet points, and code blocks where helpful
        - End with a "Further Reading" section (link titles only, no made-up URLs)
        - Be beginner-friendly but production-aware
    """).strip()

    user = textwrap.dedent(f"""
        Write comprehensive Markdown study notes for:

        TOPIC: {info['topic']}
        VIDEO: {meta['title']} by {meta['channel']}
        DATE: {date_str}

        KEY CONCEPTS: {', '.join(info['key_concepts'])}
        PREREQUISITES: {', '.join(info.get('prerequisites', []))}

        SUMMARY:
        {info['summary']}

        INDUSTRY RESEARCH SNIPPETS:
        {research}
    """).strip()

    return groq_chat([
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], max_tokens=3000, temperature=0.5)


def generate_code(meta: dict, info: dict) -> str:
    """Ask Groq to write a clean .py example file."""
    print("  [4b/5] Generating Python examples ...")
    system = textwrap.dedent("""
        You are a senior ML engineer. Write clean, well-commented Python code examples
        for the topics listed. Follow these rules:
        - Use modern Python (3.10+)
        - Include type hints
        - Use numpy, scikit-learn, or PyTorch (prefer plain numpy when possible to
          keep it dependency-light)
        - Every function has a docstring
        - Include a __main__ block that runs a minimal demo
        - Add inline comments explaining *why*, not just *what*
        - Follow PEP 8
        Output ONLY valid Python code with no markdown fences.
    """).strip()

    user = (
        f"Write Python code examples for these ML topics from the lecture "
        f"'{meta['title']}':\n"
        + "\n".join(f"- {t}" for t in info["code_topics"])
    )

    return groq_chat([
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ], max_tokens=3000, temperature=0.3)


def slugify(text: str) -> str:
    """Convert a topic name to a safe filename slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:60]


def push_to_github(filename: str, content: str, commit_msg: str) -> str:
    """
    Create or update a file in the GitHub repo via REST API.
    Returns the URL of the file on GitHub.
    """
    encoded = base64.b64encode(content.encode()).decode()
    path    = f"{NOTES_FOLDER}/{filename}"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github+json",
    }

    # Check if file already exists (need SHA to update)
    sha = None
    try:
        existing = requests.get(api_url, headers=headers, timeout=10)
        if existing.status_code == 200:
            sha = existing.json().get("sha")
    except Exception:
        pass

    payload = {
        "message": commit_msg,
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(api_url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["content"]["html_url"]


# ─────────────────────────────────────────────
# MAIN AGENT PIPELINE
# ─────────────────────────────────────────────

def run_agent(youtube_url: str):
    print(f"\n[*] ML Notes Agent starting ...\n    URL: {youtube_url}\n")

    # ── 0. Validate config ──────────────────────────────────────────────
    if "YOUR_GROQ" in GROQ_API_KEY:
        print("[ERROR] Set GROQ_API_KEY in your .env file or as an env var.")
        sys.exit(1)
    if "YOUR_GITHUB" in GITHUB_TOKEN:
        print("[ERROR] Set GITHUB_TOKEN in your .env file or as an env var.")
        sys.exit(1)

    # ── 1. Transcript ───────────────────────────────────────────────────
    video_id = extract_video_id(youtube_url)
    meta     = get_video_metadata(video_id)
    print(f"   [VIDEO] '{meta['title']}' by {meta['channel']}")

    transcript = get_transcript(video_id)

    # ── 2. Summarize ────────────────────────────────────────────────────
    info = summarize_transcript(transcript, meta)
    print(f"   [TOPIC] Topic detected: {info['topic']}")

    # ── 3. Research ─────────────────────────────────────────────────────
    research = research_topic(info["topic"], info["key_concepts"])

    # ── 4. Generate files ───────────────────────────────────────────────
    notes_md  = generate_notes(meta, info, research)
    py_code   = generate_code(meta, info) if info.get("needs_code") else None

    slug      = slugify(info["topic"])
    date_str  = datetime.now().strftime("%Y%m%d")
    md_name   = f"{date_str}_{slug}.md"
    py_name   = f"{date_str}_{slug}.py" if py_code else None

    # ── 5. Push to GitHub ───────────────────────────────────────────────
    print("  [5/5] Pushing to GitHub ...")
    commit_prefix = f"notes: add {info['topic']} ({date_str})"

    md_url = push_to_github(
        md_name,
        notes_md,
        f"{commit_prefix} – notes",
    )
    print(f"   [OK] Notes pushed  -> {md_url}")

    py_url = None
    if py_code and py_name:
        py_url = push_to_github(
            py_name,
            py_code,
            f"{commit_prefix} – code examples",
        )
        print(f"   [OK] Code pushed   -> {py_url}")

    print(f"\n[DONE] Files are live on GitHub.\n")

    return {
        "topic":    info["topic"],
        "notes":    md_url,
        "code":     py_url,
        "slug":     slug,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ml_notes_agent.py <youtube_url>")
        sys.exit(1)
    run_agent(sys.argv[1])
