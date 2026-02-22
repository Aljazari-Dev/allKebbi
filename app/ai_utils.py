# ai_utils.py
import json
import os

import requests

from app.config import ROUTER_SYSTEM_PROMPT
from app.storage import SETTINGS

# هذا هو نفس الكلاينت من الكود الأصلي (نفس الـ API key)

def openai_chat_completion(system, prompt, model=None, temperature=0.3, max_tokens=400):
    """
    Call OpenAI Chat Completions API using requests.
    Returns the assistant text or None on error.
    Expects SETTINGS['api_key'] to be set.
    """
    api_key = SETTINGS.get("api_key") or ""
    if not api_key:
        return None, "Missing OpenAI API key in settings."

    model = model or SETTINGS.get("model", "gpt-3.5-turbo")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(SETTINGS.get("temperature", temperature)),
        "max_tokens": int(SETTINGS.get("max_tokens", max_tokens)),
    }
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            return None, f"OpenAI API error {resp.status_code}: {resp.text}"
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return text, None
    except Exception as e:
        return None, str(e)


def classify_intent(user_text: str, lang: str = "ar-SA"):
    api_key = (SETTINGS.get("api_key") or "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"intent": "unknown", "need_rag": False, "assistant_reply": "Missing OpenAI API key."}

    msg = f"LANG={lang}\nTEXT={user_text}"

    payload = {
        "model": "gpt-4.1-mini",
        "temperature": 0,
        "messages": [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": msg},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if r.status_code != 200:
        return {"intent": "unknown", "need_rag": False, "assistant_reply": f"Router error {r.status_code}"}

    raw = r.json()["choices"][0]["message"]["content"]
    return json.loads(raw)
    


def lang_rule_system(lang_code: str) -> str:
    lc = (lang_code or "").lower()
    if lc.startswith("ar"):
        return (
            "LANGUAGE RULE:\n"
            "- You MUST reply ONLY in Arabic (Modern Standard Arabic). "
            "No English unless explicitly asked to translate."
        )
    else:
        return (
            "LANGUAGE RULE:\n"
            "- You MUST reply ONLY in English."
        )
