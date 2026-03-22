# Auto Notes

> Transform YouTube videos into clean, developer-friendly study notes and code examples.

Takes any educational video → extracts insights → generates concise `.md` notes + `.py` examples → publishes to your repo.

**Free to run.** Uses Groq's free tier (Llama 3.3 70B).

---

## Quick Start

### 1. Get API keys

| Service | Where | What you need |
|---------|-------|---------------|
| **Groq** | [console.groq.com](https://console.groq.com) | API key (free tier: 14,400 req/day) |
| **GitHub** | Settings → Developer settings → Tokens | Personal access token with `repo` scope |

### 2. Configure

Create `.env` file:
```bash
GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxx"
GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
GITHUB_REPO="your-username/your-repo"
```

### 3. Install & run

```bash
pip install -r requirements.txt

# Using default config
python main.py "https://youtube.com/watch?v=VIDEO_ID"

# Using ML-specific config
python main.py --config machine_learning "https://youtube.com/watch?v=VIDEO_ID"

# Save locally (no GitHub)
python main.py --output ./my-notes "https://youtube.com/watch?v=VIDEO_ID"
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Topic-agnostic** | Works for ML, web dev, finance, any domain |
| **Multi-provider** | Groq (free), Claude, extensible |
| **Configurable** | YAML configs for different domains |
| **Clean output** | Blog-style notes, no fluff, ASCII diagrams |
| **Containerized** | Docker & Docker Compose ready |

---

## Project Structure

```
.
├── core/               # Agent framework
│   ├── base_agent.py
│   ├── llm_provider.py
│   ├── prompt_template.py
│   └── content_processor.py
├── config/             # Domain configurations
│   ├── default.yaml
│   └── machine_learning.yaml
├── main.py             # CLI entry point
├── Dockerfile
└── docker-compose.yml
```

---

## Generated Output Format

Notes follow a clean, scannable structure:

```markdown
# Topic Name

> One-line hook

## The simplest way to think about it

## What it is

### Definition
### Key point
### Example

## How it works

## When to use / When to avoid

## Real-world examples

## The honest limitations

## TL;DR
```

---

## Docker Usage

```bash
# Build and run
docker-compose run --rm notes-agent "https://youtube.com/watch?v=VIDEO_ID"

# With specific config
docker-compose --profile ml run --rm notes-agent-ml "https://youtube.com/watch?v=VIDEO_ID"
```

---

## Configuration

Create custom domain configs in `config/`:

```yaml
# config/my_domain.yaml
domain: "web_development"
llm:
  provider: "groq"
  model: "llama-3.3-70b-versatile"
research:
  query_templates:
    - "{topic} best practices 2024"
    - "{topic} production examples"
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `TranscriptsDisabled` | Video has no captions. Try one with CC icon. |
| `429 Too Many Requests` | Groq rate limit. Wait 60 seconds, retry. |
| `401 Unauthorized` | Check `GROQ_API_KEY` in `.env` file. |
| GitHub 404 | Ensure `docs/` folder exists in repo. |
