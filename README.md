# youtube-summary — a Claude skill

Turn YouTube links into a structured, searchable knowledge base. Share a link with Claude and it downloads the video, takes the captions (or transcribes locally with Whisper), distills a structured card with an LLM, files it into a topical taxonomy, commits it to git, and indexes it for retrieval. Ask about your saved videos and Claude answers from the cards — with timecoded links and screenshots.

The mechanical pipeline is deterministic (plain Python scripts). The agent only chooses the engine and reads results, so there is no drift and no duplicates.

## Overview

This skill has two modes, both driven by `SKILL.md`:

- **Ingest** — a YouTube URL becomes a knowledge-base card: transcript → LLM distillation → topical classification → git commit → vector index.
- **Query** — a question is answered from the saved cards via retrieval (mini-RAG), grounded in the actual notes rather than the model's memory.

## Prerequisites

- Python 3.11
- `ffmpeg`, `yt-dlp`, and `git` on `PATH`
- An `OPENROUTER_API_KEY` for the default distill engine (or a running `ollama` for `--engine local`)
- A separate git repository for the knowledge base (your notes)

## Installation

```bash
# 1. clone the skill
git clone git@github.com:veryCoolTimo/youtube-summary-skill.git
cd youtube-summary-skill

# 2. create the environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. configure
cp config.example.yaml config.yaml      # set kb_repo, env_file, and model options

# 4. register as a Claude Code skill
ln -s "$(pwd)" ~/.claude/skills/youtube-summary
```

Restart Claude Code. The `youtube-summary` skill is now available, and Claude loads it automatically whenever you share a YouTube link.

## Usage

Talk to Claude naturally — the skill activates on its own:

- "Save this: https://youtu.be/VIDEO_ID"
- "Add these three videos to my knowledge base" (paste the links)
- "Put this one under skills/frontend"
- "Which saved video covered MCP design? What were the key points?"
- "Summarize what I saved about startups this week"

Or run the pipeline directly:

```bash
.venv/bin/python -m scripts.yt_core "https://youtu.be/VIDEO_ID" \
    [--engine openrouter|local|self] [--category skills/frontend] [--no-push]
.venv/bin/python -m scripts.kb_query "your question" --config config.yaml
```

## Features

- Captions first, automatic local Whisper (`faster-whisper`) fallback when a video has none
- Deterministic foldering into a closed taxonomy (`skills`, `reviews`, `startup`, `random`) plus subfolders from `taxonomy.yaml`; unmatched videos go to `_inbox`
- Idempotent by video id — re-running updates a card and never duplicates it
- Pluggable distillation engine: OpenRouter (default), local Ollama, or the agent itself
- Mini-RAG (chromadb + multilingual embeddings) for grounded answers
- Screenshots captured at the moments the video shows something on screen

## Distill engines

| `--engine` | Who writes the summary | Requires |
|---|---|---|
| `openrouter` (default) | Cloud Qwen (free tier) with paid fallback | `OPENROUTER_API_KEY` |
| `local` | Local `gpt-oss-20b` | a running `ollama` with the model |
| `self` | The invoking agent, to a fixed schema | nothing |

Classification, writing, dedup, indexing, and commit are always deterministic — even with `self`.

## Configuration

All options live in `config.yaml` (git-ignored, per machine): `kb_repo`, `env_file`, distill engine and models, Whisper model (`medium` by default, `large-v3` for tougher Russian audio), vector store path and embedding model, and the maximum number of screenshots per video.

## Repository structure

```
SKILL.md                 # the skill manifest (name, description, protocol)
config.example.yaml      # config template
taxonomy.example.yaml    # default folder taxonomy
scripts/                 # the deterministic pipeline (transcript, distill, classify, write, vectorize, query)
tests/                   # pytest unit suite
docs/superpowers/        # design spec and implementation plans
```

## Testing

```bash
.venv/bin/pytest -q
```

Unit tests mock network and model calls; the no-duplicates guarantee is covered in `tests/test_kb_writer.py` and `tests/test_yt_core.py`.

## License

MIT — see [LICENSE](LICENSE).
