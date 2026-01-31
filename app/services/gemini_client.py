from __future__ import annotations

import json

import google.generativeai as genai


def analyze_paper(
    api_key: str,
    thesis_topic: str,
    title: str,
    abstract: str,
) -> tuple[float | None, str | None, str | None]:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = (
        "Aşağıdaki makaleyi tez konusuna göre değerlendir.\n"
        f"Tez konusu: {thesis_topic}\n\n"
        f"Başlık: {title}\n"
        f"Özet: {abstract or 'Özet yok.'}\n\n"
        "Yanıtı sadece JSON olarak ver. Anahtarlar: score (0-100 sayı), summary (1-2 cümle Türkçe), tags (3 kısa etiket)."
    )

    response = model.generate_content(prompt)
    text = response.text or ""

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # try to extract JSON from text
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None, None, None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None, None, None

    score = data.get("score")
    summary = data.get("summary")
    tags = data.get("tags")
    if isinstance(tags, list):
        tags = ", ".join(tags)

    try:
        score_value = float(score) if score is not None else None
    except (ValueError, TypeError):
        score_value = None

    return score_value, summary, tags if isinstance(tags, str) else None
