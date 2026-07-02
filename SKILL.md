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
Pass ALL the user's URLs in one command (one venv start, one git commit):
```bash
cd ~/.claude/skills/youtube-summary && .venv/bin/python -m scripts.yt_core "<url1>" "<url2>" --config config.yaml
```
- Default engine `openrouter`. Add `--engine local` (private, via ollama — distill AND classify stay offline) or `--engine self` (you summarize, see below) only if asked.
- Force a folder with `--category top/sub` only if the user specifies it; otherwise it auto-classifies. Tops come from `taxonomy.yaml` in the KB repo (default: skills, reviews, startup, random).
- Output: one JSON line per video, then always a final `{"git": ..., "videos": N}` line (`videos` = how many were saved/refiled). Statuses:
  - `ok` — saved; `title`, `tldr`, `file`, `top/sub` are in the line — report from them, no need to read the card.
  - `exists` — already in the KB; nothing re-run. Tell the user; add `--force` to re-process, or pass `--category top/sub` to move it (cheap re-file, no LLM).
  - `refiled` — an existing card was moved to the requested category.
  - `need_card` — engine=self only, see protocol below.
  - `failed` — report `reason` to the user (this includes a typo'd `--category`: the pipeline refuses rather than guessing).
- `git` in the final line: `pushed` is full success; `committed` = saved locally, push disabled (`--no-push`); `clean` = nothing changed (e.g. `--force` produced identical content) — fine, not an error; `push_failed` = committed locally but not pushed — tell the user; `failed` = the commit itself failed; `skipped` = nothing was saved so no commit was attempted; `disabled` = the KB folder is a plain directory (default no-git setup) — normal, but if the user asks about syncing/versioning, offer to `git init` it.
- If something landed in `<top>/_inbox` (no taxonomy match), say so and offer to add a subfolder to `taxonomy.yaml`.

### engine=self protocol (you are the summarizer)
1. Run the ingest command with `--engine self` → each video answers `{"status":"need_card","prompt_file":...}`.
2. Read `prompt_file` (SYSTEM + USER sections), write the card strictly to that JSON schema, including the `category` field, into a temp file.
3. Rerun with `--card-file <path>` and that video's SINGLE url — the pipeline continues (classify → write → index → commit). With several videos, do one rerun per video.

## QUERY — questions → grounded answer
Never answer from memory. Follow every step:
1. **Retrieve:** `cd ~/.claude/skills/youtube-summary && .venv/bin/python -m scripts.kb_query "<question>" --config config.yaml`
   - Hybrid search: vector + keyword over the cards; returned `file`/`media_dir` paths are absolute.
   - "что я сохранял недавно / на этой неделе" → use `--recent N` (newest first) instead of a question; `--top skills` filters by category.
2. **Read** the actual card files (the `file` paths returned) — the full card, not just the snippet.
3. **Verify** every claim you make is present in a card you read. Not found → say so, don't invent.
4. **Answer** concisely: video title, timecoded deep-links from `takeaways`, and the screenshot (`media_dir`) when the question is visual.

## Output rules
- "Только важное / без воды" → use `tldr` + key takeaways, not everything.
- "Не повторяй прежнее" → don't resend a card already shown earlier in this conversation.
- "Подробнее про это видео" → read its full card and expand only from there.

## Maintenance
- New machine / empty search results but cards exist → rebuild the vector index without any LLM calls:
  `.venv/bin/python -m scripts.reindex --config config.yaml`

## Config & secrets
`config.yaml` (gitignored, per-machine) sets `kb_repo` (empty = `knowledge-base/` folder next to the skill, no git; a git clone path = auto commit+push), distill engine/models and card language, caption language priority, Whisper model, vector store, embedder. `OPENROUTER_API_KEY` comes from `env_file` or the environment. See `README.md` for setup.
