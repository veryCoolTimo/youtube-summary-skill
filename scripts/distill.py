import json, re, sys, urllib.request

OR_URL = "https://openrouter.ai/api/v1/chat/completions"

DISTILL_SYS_PROMPT = (
    "Ты делаешь выжимку YouTube-видео для занятого разработчика (рус/англ контент). "
    "Дан транскрипт, числа в [скобках] — секунды от начала. "
    "Верни СТРОГО валидный JSON без markdown-обёртки по схеме:\n"
    '{"verdict":"watch_full|digest_enough|skip","verdict_ru":"короткая фраза",'
    '"tldr":"простыми словами, как другу: что за штука/инструмент, что делает, где пригодится. 2-4 предложения",'
    '"summary":"для архива: о чём видео и ключевая логика (3-5 предложений)",'
    '"takeaways":[{"point":"инсайт","ts":секунды}],'
    '"applicable":["конкретное применимое: что попробовать"],'
    '"theme":"короткая свободная подпись темы",'
    '"visual_moments":[{"ts":секунды,"why":"что показывают на экране"}]}\n'
    "Правила: пиши без воды и рекламного пафоса самого ролика; конкретика вместо хайпа; "
    "для инструментов: что делает -> где нужно -> нюансы/плюсы автора; "
    "для опыт/стартап-роликов: что испытал автор, сложности, что важное запомнить; "
    "3-6 takeaways с реальными ts; applicable 0-4; visual_moments 0-3 только где явно показывают экран/демо/код; "
    "не выдумывай, бери только из транскрипта; пиши по-русски."
)


def build_user_prompt(meta: dict, segs: list) -> str:
    lines = [f"[{int(s['start'])}] {s['text']}" for s in segs if s.get("text", "").strip()]
    transcript = "\n".join(lines)
    if len(transcript) > 90000:
        transcript = transcript[:90000] + "\n…[обрезано]"
    return f"НАЗВАНИЕ: {meta.get('title','?')}\nКАНАЛ: {meta.get('channel','?')}\n\nТРАНСКРИПТ:\n{transcript}"


def parse_card(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(m.group(0) if m else raw)


def _openrouter_chat(model, messages, key, timeout=120) -> str:
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.3}).encode()
    req = urllib.request.Request(OR_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "HTTP-Referer": "https://youtube-summary-skill.local", "X-Title": "yt-skill"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]


def openrouter_chat_fallback(models, messages, key) -> tuple[str, str]:
    """Try each model in order; return (model, content). Raises if all fail."""
    last = None
    for model in models:
        try:
            return model, _openrouter_chat(model, messages, key)
        except Exception as e:
            last = e
            sys.stderr.write(f"[openrouter {model} failed: {str(e)[:160]}]\n")
    raise RuntimeError(f"all openrouter models failed: {last}")


def _ollama_chat(model, messages, timeout=600) -> str:
    body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["message"]["content"]


def distill(meta: dict, segs: list, cfg: dict, key: str, self_fn=None) -> dict:
    sys_p, usr_p = DISTILL_SYS_PROMPT, build_user_prompt(meta, segs)
    msgs = [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}]
    engine = cfg["distill"]["engine"]
    if engine == "self":
        if not self_fn:
            raise RuntimeError("engine=self requires self_fn callback")
        card = parse_card(self_fn(sys_p, usr_p))
        card["_engine"] = "self"
        return card
    if engine == "local":
        card = parse_card(_ollama_chat(cfg["distill"]["local_model"], msgs))
        card["_engine"] = "local:" + cfg["distill"]["local_model"]
        return card
    model, raw = openrouter_chat_fallback(cfg["distill"]["openrouter_models"], msgs, key)
    card = parse_card(raw)
    card["_engine"] = "openrouter:" + model
    return card
