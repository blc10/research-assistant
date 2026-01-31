from __future__ import annotations

import logging
import re
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from ..config import load_config
from ..db import ensure_defaults, get_setting, set_setting
from ..task_parser import looks_like_task, parse_duration, parse_task_text
from ..utils import format_dt_local, from_iso_to_local, now_local, parse_time_str, to_utc_iso
from .goal_service import create_goal, list_goals
from .paper_scanner import scan_papers
from .paper_service import count_papers, list_papers_since, mark_read
from .task_service import (
    add_pending_task,
    clear_pending_task,
    count_tasks,
    create_task,
    delete_task,
    due_tasks_for_reminder,
    get_pending_task,
    get_task,
    list_tasks,
    list_tasks_between,
    mark_done,
    snooze_task,
    set_reminded,
)


CONFIG = load_config()
BOT_NAME = "Research Assistant"
BOT_ROLE = "Kişisel araştırma asistanın."

SUMMARY_TASK_LIMIT = 6
SUMMARY_PAPER_LIMIT = 6

TEMPLATE_EXAMPLES = [
    "Bana yarın 15:00 danışman toplantısını hatırlat",
    "Bu hafta tez önerisini bitirmeyi hatırlat",
    "Bugün 18:00 markete gitmemi hatırlat",
    "Şu hatırlatmayı sil: danışman toplantısı",
    "Özet",
]


def _format_task_line(task: dict) -> str:
    due = None
    if task.get("due_at"):
        due = format_dt_local(from_iso_to_local(task["due_at"]))
    else:
        due = "(tarih yok)"
    return f"#{task['id']} • {task['title']} — {due}"


def _format_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return "Görev bulunamadı."
    lines = ["Görevler:"]
    lines.extend(_format_task_line(task) for task in tasks)
    return "\n".join(lines)


def _get_chat_id(update: Update) -> str:
    chat_id = str(update.effective_chat.id)
    stored = get_setting("telegram_chat_id")
    if not stored:
        set_setting("telegram_chat_id", chat_id)
    return stored or chat_id


def _truncate(text: str, limit: int = 36) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _normalize_task_title(title: str) -> str:
    text = title.strip()
    if not text:
        return "Görev."

    lowered = text.lower()
    lowered = re.sub(r"\b(bana|beni|bize|bizim|lütfen|lutfen|hatırlat|hatirlat)\b", " ", lowered)
    lowered = re.sub(r"\b(şunu|şu|bunu|bana|beni|hatırlatma|hatirlatma|görev|görevi)\b", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()

    replacements = {
        "yapacağımı": "yapılacak",
        "yapacağım": "yapılacak",
        "gideceğimi": "gidilecek",
        "gideceğim": "gidilecek",
        "tamamlayacağımı": "tamamlanacak",
        "tamamlayacağım": "tamamlanacak",
        "hazırlayacağımı": "hazırlanacak",
        "hazırlayacağım": "hazırlanacak",
        "göndereceğimi": "gönderilecek",
        "göndereceğim": "gönderilecek",
    }
    for src, dst in replacements.items():
        lowered = lowered.replace(src, dst)

    if lowered.endswith("yapmak"):
        lowered = lowered[: -len("yapmak")].strip() + " yapılacak"
    if lowered.endswith("gitmek"):
        lowered = lowered[: -len("gitmek")].strip() + " gidilecek"

    cleaned = lowered.strip().capitalize()
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _tokenize(text: str) -> set[str]:
    return {token for token in re.split(r"[^\\wçğıöşüÇĞİÖŞÜ]+", text.lower()) if len(token) > 2}


def _extract_action_query(text: str, action_words: list[str]) -> str:
    cleaned = text.lower()
    for word in action_words:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(
        r"\b(şu|bunu|şunu|bu|o|hatırlatma|hatirlatma|görev|görevi|hatırlatmayı|hatirlatmayi)\b",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"#?\\d+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _find_task_candidates(query: str, limit: int = 5) -> list[dict]:
    tasks = list_tasks(limit=50)
    if not tasks:
        return []
    if not query:
        return tasks[:limit]

    query_tokens = _tokenize(query)
    scored: list[tuple[int, dict]] = []
    for task in tasks:
        title = task["title"].lower()
        score = 0
        if query in title:
            score += 3
        title_tokens = _tokenize(title)
        score += len(query_tokens & title_tokens)
        if score > 0:
            scored.append((score, task))

    scored.sort(key=lambda item: (-item[0], item[1].get("due_at") is None))
    return [task for _, task in scored[:limit]]


async def _send_task_selection(message, tasks: list[dict], action: str) -> None:
    if not tasks:
        await message.reply_text("Eşleşen görev bulunamadı. /tasks ile listeden bakabilirsin.")
        return
    prefix = "delete" if action == "delete" else "done"
    keyboard = []
    for task in tasks:
        label = f"#{task['id']} {_truncate(task['title'], 32)}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"{prefix}_pick:{task['id']}")])
    keyboard.append([InlineKeyboardButton("Vazgeç", callback_data=f"{prefix}:cancel")])
    await message.reply_text("Hangisini seçeyim?", reply_markup=InlineKeyboardMarkup(keyboard))


async def _send_delete_confirmation(message, task_id: int) -> None:
    task = get_task(task_id)
    if not task:
        await message.reply_text("Görev bulunamadı.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Sil", callback_data=f"delete:{task_id}"),
                InlineKeyboardButton("Vazgeç", callback_data="delete:cancel"),
            ]
        ]
    )
    await message.reply_text(
        f"#{task_id} silinsin mi?\n{task['title']}",
        reply_markup=keyboard,
    )


async def _send_done_confirmation(message, task_id: int) -> None:
    task = get_task(task_id)
    if not task:
        await message.reply_text("Görev bulunamadı.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Tamamlandı", callback_data=f"done:{task_id}"),
                InlineKeyboardButton("Vazgeç", callback_data="done:cancel"),
            ]
        ]
    )
    await message.reply_text(
        f"#{task_id} tamamlandı olarak işaretlensin mi?\n{task['title']}",
        reply_markup=keyboard,
    )


def _build_summary() -> str:
    now = now_local()
    pending_total = count_tasks("pending")
    done_total = count_tasks("done")

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    today_tasks = list_tasks_between(to_utc_iso(start), to_utc_iso(end))
    upcoming = list_tasks(limit=SUMMARY_TASK_LIMIT)

    since = to_utc_iso(now - timedelta(hours=24))
    papers = list_papers_since(since, limit=SUMMARY_PAPER_LIMIT)
    paper_total = count_papers()

    lines = [
        f"📊 {BOT_NAME} Özeti",
        f"Açık görev: {pending_total} | Tamamlanan: {done_total}",
    ]
    if today_tasks:
        lines.append("Bugün:")
        for task in today_tasks[:SUMMARY_TASK_LIMIT]:
            lines.append(f"• {_format_task_line(task)}")
    elif upcoming:
        lines.append("Yaklaşan görevler:")
        for task in upcoming[:SUMMARY_TASK_LIMIT]:
            lines.append(f"• {_format_task_line(task)}")
    else:
        lines.append("Görev görünmüyor.")

    if papers:
        lines.append("Son makaleler:")
        for paper in papers:
            score = paper.get("relevance_score")
            score_text = f"{score:.0f}/100" if isinstance(score, (int, float)) else "skor yok"
            lines.append(f"• {paper['title']} ({score_text})")
    else:
        lines.append("Son 24 saatte makale yok.")

    lines.append(f"Toplam makale: {paper_total}")
    return "\n".join(lines)


def _is_summary_request(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ["özet", "ozet", "summary", "rapor", "durum"])


def _is_delete_request(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ["sil", "kaldır", "iptal et", "silmek"])


def _is_complete_request(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ["tamamlandı", "tamamladım", "tamamla", "bitirdim", "bitti"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults()
    chat_id = _get_chat_id(update)
    await update.message.reply_text(
        f"Merhaba! Ben {BOT_NAME}. {BOT_ROLE}\n"
        "Örnek: 'yarın saat 3'te danışman toplantısı var hatırlat' ya da 'bu hafta thesis proposal bitir'.\n"
        "Komutlar: /tasks, /today, /week, /done <id>, /delete <id>, /snooze <id> 2 saat, /summary, /papers, /goals, /goal",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Komutlar:\n"
        "/tasks - tüm açık görevler\n"
        "/today - bugünkü görevler\n"
        "/week - bu haftaki görevler\n"
        "/done <id> - görevi tamamla\n"
        "/delete <id> - görevi sil\n"
        "/snooze <id> 2 saat - ertele\n"
        "/summary - görev ve makale özeti\n"
        "/templates - örnek cümleler\n"
        "/papers - yeni makaleler\n"
        "/goals - yıllık hedefler\n"
        "/goal <yıl> <hedef> - yeni hedef ekle\n"
        "/scan - makale taramasını şimdi başlat\n"
        "/read <id> - makale okundu olarak işaretle\n"
    )


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = list_tasks()
    await update.message.reply_text(_format_tasks(tasks))


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = now_local()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    tasks = list_tasks_between(to_utc_iso(start), to_utc_iso(end))
    await update.message.reply_text(_format_tasks(tasks))


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = now_local()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=6, hours=23, minutes=59)
    tasks = list_tasks_between(to_utc_iso(start), to_utc_iso(end))
    await update.message.reply_text(_format_tasks(tasks))


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Örnek: /done 12")
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Geçersiz görev ID.")
        return

    if mark_done(task_id):
        await update.message.reply_text(f"#{task_id} tamamlandı ✅")
    else:
        await update.message.reply_text("Görev bulunamadı.")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Örnek: /delete 12")
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Geçersiz görev ID.")
        return

    await _send_delete_confirmation(update.message, task_id)


async def snooze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Örnek: /snooze 12 2 saat")
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Geçersiz görev ID.")
        return

    duration_text = " ".join(context.args[1:])
    minutes = parse_duration(duration_text)
    if minutes is None:
        await update.message.reply_text("Süreyi anlayamadım. Örnek: 30 dk, 2 saat, 1 gün")
        return

    task = get_task(task_id)
    if not task:
        await update.message.reply_text("Görev bulunamadı.")
        return

    base = now_local()
    if task.get("due_at"):
        base = from_iso_to_local(task["due_at"])
    new_due = base + timedelta(minutes=minutes)
    snooze_task(task_id, new_due)
    await update.message.reply_text(f"#{task_id} yeni zaman: {format_dt_local(new_due)}")


async def papers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    since = to_utc_iso(now_local() - timedelta(hours=24))
    papers = list_papers_since(since, limit=CONFIG.max_papers_per_day)
    if not papers:
        await update.message.reply_text("Yeni makale bulunamadı.")
        return

    lines = ["Yeni makaleler:"]
    for paper in papers:
        score = paper.get("relevance_score")
        score_text = f"{score:.0f}/100" if isinstance(score, (int, float)) else "skor yok"
        lines.append(f"#{paper['id']} • {paper['title']} ({score_text})")
        if paper.get("url"):
            lines.append(paper["url"])
    await update.message.reply_text("\n".join(lines))


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_build_summary())


async def templates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["Örnek kalıplar:"]
    lines.extend(f"• {example}" for example in TEMPLATE_EXAMPLES)
    await update.message.reply_text("\n".join(lines))


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    goals = list_goals()
    if not goals:
        await update.message.reply_text("Henüz hedef yok. /goal <yıl> <hedef> ile ekleyebilirsin.")
        return
    lines = ["Yıllık hedefler:"]
    for goal in goals:
        lines.append(f"#{goal['id']} • {goal['year']} — {goal['title']} (%{goal['progress']})")
    await update.message.reply_text("\n".join(lines))


async def goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Örnek: /goal 2026 3 makale yayınla")
        return
    year_text = context.args[0]
    if not year_text.isdigit():
        await update.message.reply_text("Yıl formatı geçersiz. Örnek: /goal 2026 ...")
        return
    title = " ".join(context.args[1:]).strip()
    if not title:
        await update.message.reply_text("Hedef metni eksik.")
        return
    create_goal(title, int(year_text))
    await update.message.reply_text("Hedef eklendi ✅")


async def read_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Örnek: /read 42")
        return
    try:
        paper_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Geçersiz makale ID.")
        return

    mark_read(paper_id, to_utc_iso(now_local()))
    await update.message.reply_text(f"Makale #{paper_id} okundu olarak işaretlendi.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    chat_id = _get_chat_id(update)
    now = now_local()
    lowered = text.lower()

    pending = get_pending_task(chat_id)
    if pending:
        title = pending["title"]
        parsed_title, due_at = parse_task_text(text, now)
        if due_at is None:
            await update.message.reply_text("Zamanı anlayamadım. Örnek: yarın 15:00")
            return
        create_task(title, due_at, source="telegram")
        clear_pending_task(pending["id"])
        await update.message.reply_text(
            f"Kaydettim.\nGörev: {title}\nZaman: {format_dt_local(due_at)}"
        )
        return

    if _is_summary_request(text):
        await update.message.reply_text(_build_summary())
        return

    if "şablon" in lowered or "template" in lowered or "örnek" in lowered:
        await templates_command(update, context)
        return

    if _is_delete_request(text):
        match = re.search(r"#?(\\d+)", text)
        if match:
            task_id = int(match.group(1))
            await _send_delete_confirmation(update.message, task_id)
            return
        query = _extract_action_query(text, ["sil", "kaldır", "iptal et", "silmek"])
        candidates = _find_task_candidates(query)
        if len(candidates) == 1:
            await _send_delete_confirmation(update.message, candidates[0]["id"])
        else:
            await _send_task_selection(update.message, candidates, "delete")
        return

    if _is_complete_request(text):
        match = re.search(r"#?(\\d+)", text)
        if match:
            task_id = int(match.group(1))
            await _send_done_confirmation(update.message, task_id)
            return
        query = _extract_action_query(text, ["tamamla", "tamamlandı", "tamamladım", "bitirdim", "bitti"])
        candidates = _find_task_candidates(query)
        if len(candidates) == 1:
            await _send_done_confirmation(update.message, candidates[0]["id"])
        else:
            await _send_task_selection(update.message, candidates, "done")
        return

    if looks_like_task(text):
        title, due_at = parse_task_text(text, now)
        normalized_title = _normalize_task_title(title)
        if due_at is None:
            add_pending_task(chat_id, normalized_title, to_utc_iso(now))
            await update.message.reply_text("Ne zaman hatırlatayım?")
            return
        create_task(normalized_title, due_at, source="telegram")
        await update.message.reply_text(
            f"Kaydettim.\nGörev: {normalized_title}\nZaman: {format_dt_local(due_at)}"
        )
        return

    if "listele" in lowered or "görev" in lowered or "liste" in lowered:
        tasks = list_tasks()
        await update.message.reply_text(_format_tasks(tasks))
        return

    if "hedef" in lowered:
        match = re.search(r"(20\\d{2})", text)
        if match:
            year = int(match.group(1))
            title = text.replace(match.group(1), "").strip()
            if title:
                create_goal(title, year)
                await update.message.reply_text("Hedef eklendi ✅")
                return

    if any(word in lowered for word in ["merhaba", "selam", "naber", "nasılsın", "nasilsin"]):
        await update.message.reply_text(f"Merhaba! Ben {BOT_NAME}. Sana nasıl yardımcı olabilirim?")
        return

    if any(word in lowered for word in ["teşekkür", "tesekkur", "sağ ol", "sag ol"]):
        await update.message.reply_text("Rica ederim. Başka bir şey var mı?")
        return

    if any(word in lowered for word in ["kimsin", "nesin", "ne yaparsın"]):
        await update.message.reply_text(f"Ben {BOT_NAME}. Görevlerini ve araştırma özetlerini yönetiyorum.")
        return

    await update.message.reply_text(
        f"{BOT_NAME} burada. Görev eklemek için örnek: 'yarın 10:00 toplantı var hatırlat'. "
        "İstersen 'özet' yaz, durumunu toparlayayım."
    )


async def reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now_iso = to_utc_iso(now_local())
    due_tasks = due_tasks_for_reminder(now_iso)
    if not due_tasks:
        return

    chat_id = get_setting("telegram_chat_id")
    if not chat_id:
        return

    for task in due_tasks:
        due_text = ""
        if task.get("due_at"):
            due_text = format_dt_local(from_iso_to_local(task["due_at"]))
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Tamamlandı", callback_data=f"done:{task['id']}"),
                    InlineKeyboardButton("1 saat ertele", callback_data=f"snooze:{task['id']}:60"),
                ]
            ]
        )
        message = (
            "⏰ Hatırlatma\n"
            f"Görev: {task['title']}\n"
            f"Zaman: {due_text or 'Belirtilmedi'}\n"
            "İstersen aşağıdan işlem seçebilirsin."
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=keyboard,
        )
        set_reminded(task["id"], now_iso)


async def scan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    results = scan_papers()
    logging.getLogger(__name__).info("Paper scan completed: %s", results)


async def digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = get_setting("telegram_chat_id")
    if not chat_id:
        return

    now = now_local()
    since = to_utc_iso(now - timedelta(hours=24))
    papers = list_papers_since(since, limit=CONFIG.max_papers_per_day)
    if not papers:
        await context.bot.send_message(chat_id=chat_id, text="Bugün yeni makale yok gibi görünüyor.")
        return

    lines = ["📌 Günlük makale özeti:"]
    for paper in papers:
        score = paper.get("relevance_score")
        score_text = f"{score:.0f}/100" if isinstance(score, (int, float)) else "skor yok"
        summary = paper.get("summary") or ""
        lines.append(f"• {paper['title']} ({score_text})")
        if summary:
            lines.append(f"  {summary}")
        if paper.get("url"):
            lines.append(paper["url"])
    message = "\n".join(lines)

    # Telegram message length limit safety
    if len(message) > 3800:
        parts = ["\n".join(lines[:10]), "\n".join(lines[10:])]
        for part in parts:
            if part.strip():
                await context.bot.send_message(chat_id=chat_id, text=part)
    else:
        await context.bot.send_message(chat_id=chat_id, text=message)


async def manual_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Tarama başlıyor...")
    results = scan_papers()
    await update.message.reply_text(
        f"Tarama tamamlandı. Yeni: {results['new_papers']}, analiz edilen: {results['analyzed']}"
    )


def build_application():
    log_level = getattr(logging, CONFIG.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)
    ensure_defaults()

    app = ApplicationBuilder().token(CONFIG.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("week", week_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("snooze", snooze_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(CommandHandler("ozet", summary_command))
    app.add_handler(CommandHandler("templates", templates_command))
    app.add_handler(CommandHandler("papers", papers_command))
    app.add_handler(CommandHandler("goals", goals_command))
    app.add_handler(CommandHandler("goal", goal_command))
    app.add_handler(CommandHandler("read", read_command))
    app.add_handler(CommandHandler("scan", manual_scan))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Schedule jobs
    job_queue = app.job_queue
    job_queue.run_repeating(reminder_job, interval=60, first=10, name="reminders")
    job_queue.run_daily(scan_job, time=parse_time_str(CONFIG.paper_scan_time), name="scan")
    job_queue.run_daily(digest_job, time=parse_time_str(CONFIG.morning_digest_time), name="digest")

    return app


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if data in {"delete:cancel", "done:cancel"}:
        await query.edit_message_text("İşlem iptal edildi.")
        return

    if data.startswith("delete_pick:"):
        try:
            task_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text("Geçersiz işlem.")
            return
        await _send_delete_confirmation(query.message, task_id)
        return

    if data.startswith("done_pick:"):
        try:
            task_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text("Geçersiz işlem.")
            return
        await _send_done_confirmation(query.message, task_id)
        return

    if data.startswith("delete:"):
        try:
            task_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text("Geçersiz işlem.")
            return

        if delete_task(task_id):
            await query.edit_message_text(f"#{task_id} silindi 🗑️")
        else:
            await query.edit_message_text("Görev bulunamadı.")
        return

    if data.startswith("done:"):
        try:
            task_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text("Geçersiz işlem.")
            return

        if mark_done(task_id):
            await query.edit_message_text(f"#{task_id} tamamlandı ✅")
        else:
            await query.edit_message_text("Görev bulunamadı.")
        return

    if data.startswith("snooze:"):
        try:
            _, task_id_text, minutes_text = data.split(":", 2)
            task_id = int(task_id_text)
            minutes = int(minutes_text)
        except ValueError:
            await query.edit_message_text("Geçersiz işlem.")
            return

        task = get_task(task_id)
        if not task:
            await query.edit_message_text("Görev bulunamadı.")
            return
        base = now_local()
        if task.get("due_at"):
            base = from_iso_to_local(task["due_at"])
        new_due = base + timedelta(minutes=minutes)
        snooze_task(task_id, new_due)
        await query.edit_message_text(f"#{task_id} yeni zaman: {format_dt_local(new_due)}")
        return
