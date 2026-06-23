---
name: youtube-summary
description: Use when the user shares one or more YouTube links to save/summarize, or asks about previously saved YouTube videos (what was in video X, which video covered Y, find the one about Z). Covers ingesting links into the knowledge base and answering questions from the saved cards.
---

# youtube-summary

Single entry point for the YouTube knowledge base. The pipeline is deterministic (scripts in this repo) — you pick the engine and read results; you never write cards or edit the index by hand.

**REPO** (run everything from here, it has its own venv with all deps):
`cd ~/.claude/skills/youtube-summary` then use `.venv/bin/python`.
(This is the install path from the README; adjust if the repo lives elsewhere.)

## When to use
- The user shares YouTube link(s) → **INGEST** them.
- The user asks about saved videos → **QUERY** the knowledge base.

## INGEST — links → knowledge base
For each URL the user sends:
```bash
cd ~/.claude/skills/youtube-summary && .venv/bin/python -m scripts.yt_core "<url>" --config config.yaml
```
- Default engine `openrouter`. Add `--engine local` (private gpt-oss-20b) or `--engine self` (you summarize) only if asked.
- Force a folder with `--category top/sub` (top ∈ skills, reviews, startup, random) only if the user specifies it; otherwise it auto-classifies.
- Output: one JSON line per video `{status, vid, file, top, sub, source, engine}`. Idempotent — re-running updates, never duplicates.
- Report briefly: what was added/updated and where. If something landed in `<top>/_inbox` (no taxonomy match), say so and offer to add a subfolder to `taxonomy.yaml`.

## QUERY — questions → grounded answer
Never answer from memory. Follow every step:
1. **Retrieve:** `cd ~/.claude/skills/youtube-summary && .venv/bin/python -m scripts.kb_query "<question>" --config config.yaml`
2. **Read** the actual card files (the `file` paths returned) — the full card, not just the snippet.
3. **Verify** every claim you make is present in a card you read. Not found → say so, don't invent.
4. **Answer** concisely: video title, timecoded deep-links from `takeaways`, and the screenshot (`media_dir`) when the question is visual.

## Output rules
- "Только важное / без воды" → use `tldr` + key takeaways, not everything.
- "Не повторяй прежнее" → don't resend a card already shown earlier in this conversation.
- "Подробнее про это видео" → read its full card and expand only from there.

## Config & secrets
`config.yaml` (gitignored, per-machine) sets `kb_repo`, distill engine/models, Whisper model, vector store, embedder. `OPENROUTER_API_KEY` comes from `env_file` or the environment. See `README.md` for setup.
