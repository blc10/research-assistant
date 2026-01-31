from __future__ import annotations

from datetime import timedelta

from flask import Flask, redirect, render_template, request, url_for

from ..config import load_config
from ..db import ensure_defaults, get_setting, set_setting
from ..task_parser import parse_task_text
from ..utils import format_dt_local, from_iso_to_local, now_local, to_utc_iso
from ..services.goal_service import create_goal, list_goals
from ..services.paper_service import count_papers, count_tasks, list_papers, list_papers_since, mark_read
from ..services.stats_service import get_read_streak
from ..services.task_service import create_task, delete_task, list_tasks, list_tasks_between, mark_done


CONFIG = load_config()


def create_app() -> Flask:
    ensure_defaults()
    app = Flask(__name__)
    app.config["WEB_HOST"] = CONFIG.web_host
    app.config["WEB_PORT"] = CONFIG.web_port
    app.secret_key = CONFIG.web_secret_key

    @app.route("/")
    def dashboard():
        now = now_local()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        today_tasks = list_tasks_between(to_utc_iso(start), to_utc_iso(end))
        pending_tasks = list_tasks(limit=8)
        streak = get_read_streak()
        recent_papers = list_papers_since(to_utc_iso(now - timedelta(hours=24)), limit=5)
        stats = {
            "pending_tasks": count_tasks("pending"),
            "done_tasks": count_tasks("done"),
            "new_papers": count_papers("new"),
            "read_papers": count_papers("read"),
        }
        return render_template(
            "dashboard.html",
            now=now,
            today_tasks=today_tasks,
            pending_tasks=pending_tasks,
            recent_papers=recent_papers,
            streak=streak,
            stats=stats,
        )

    @app.route("/tasks", methods=["GET", "POST"])
    def tasks():
        if request.method == "POST":
            text = request.form.get("task_text", "").strip()
            if text:
                title, due_at = parse_task_text(text, now_local())
                create_task(title, due_at, source="web")
            return redirect(url_for("tasks"))

        tasks_list = list_tasks(limit=50)
        return render_template("tasks.html", tasks=tasks_list, format_dt_local=_format_dt)

    @app.route("/tasks/<int:task_id>/done", methods=["POST"])
    def task_done(task_id: int):
        mark_done(task_id)
        return redirect(url_for("tasks"))

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    def task_delete(task_id: int):
        delete_task(task_id)
        return redirect(url_for("tasks"))

    @app.route("/papers")
    def papers():
        status = request.args.get("status")
        papers_list = list_papers(status=status, limit=60)
        return render_template("papers.html", papers=papers_list)

    @app.route("/papers/<int:paper_id>/read", methods=["POST"])
    def paper_read(paper_id: int):
        mark_read(paper_id, to_utc_iso(now_local()))
        return redirect(url_for("papers"))

    @app.route("/stats")
    def stats():
        streak = get_read_streak()
        return render_template("stats.html", streak=streak)

    @app.route("/goals", methods=["GET", "POST"])
    def goals():
        if request.method == "POST":
            title = request.form.get("goal_title", "").strip()
            year_text = request.form.get("goal_year", "").strip()
            if title and year_text.isdigit():
                create_goal(title, int(year_text))
            return redirect(url_for("goals"))

        goals_list = list_goals()
        return render_template("goals.html", goals=goals_list)

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            thesis_topic = request.form.get("thesis_topic", "").strip()
            keywords = request.form.get("paper_keywords", "").strip()
            if thesis_topic:
                set_setting("thesis_topic", thesis_topic)
            if keywords:
                set_setting("paper_keywords", keywords)
            return redirect(url_for("settings"))

        return render_template(
            "settings.html",
            thesis_topic=get_setting("thesis_topic") or "",
            paper_keywords=get_setting("paper_keywords") or "",
        )

    return app


def _format_dt(iso_value: str | None) -> str:
    if not iso_value:
        return "(tarih yok)"
    return format_dt_local(from_iso_to_local(iso_value))
