# Research Assistant

A personal research assistant that manages natural‑language tasks via Telegram and delivers daily paper digests by scanning arXiv and Semantic Scholar. It includes a web dashboard for tasks, papers, goals, and reading stats.

## Highlights
- Telegram bot for natural‑language tasks and reminders
- Daily arXiv + Semantic Scholar scanning
- Gemini‑based relevance score + short summary
- Morning Telegram digest
- Flask web dashboard (tasks, papers, goals, stats)
- SQLite storage
- Optional systemd services for 24/7 operation

## Screens / Demo
- Web UI: `http://localhost:8080`
- Telegram bot: chat with your bot directly

## Quickstart
1) Install Python 3.11+ and venv
2) Create `.env` from `.env.example`
3) Put your API keys in `.env`
4) Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5) Run:

```bash
python scripts/run_bot.py
python scripts/run_web.py
```

## Configuration
Edit `.env` to set:
- `TELEGRAM_BOT_TOKEN`
- `GEMINI_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY` (optional)
- `THESIS_TOPIC` and `PAPER_KEYWORDS`
- `TIMEZONE`, `PAPER_SCAN_TIME`, `MORNING_DIGEST_TIME`

> API keys are **not** included. Add your own keys in `.env`.

## Telegram Bot Commands
- `/tasks` - list pending tasks
- `/today` - today’s tasks
- `/week` - this week’s tasks
- `/done <id>` - mark task done
- `/delete <id>` - delete task (with confirmation)
- `/snooze <id> 2 hours` - postpone
- `/summary` - tasks + papers summary
- `/papers` - list recent papers
- `/read <id>` - mark paper as read
- `/goals` - list goals
- `/goal <year> <text>` - add goal
- `/templates` - show example prompts

Natural language examples:
- “remind me about advisor meeting tomorrow at 15:00”
- “finish thesis proposal this week”
- “delete the reminder about advisor meeting”
- “summary”

## Web Dashboard
- Tasks: add, mark done, delete
- Papers: list, open, mark read
- Goals: create yearly goals
- Settings: update thesis topic / keywords

## Desktop Launcher (Ubuntu)
A desktop shortcut starts the bot + web UI and opens the dashboard:
- Launcher script: `launcher/start_assistant.sh`
- Desktop shortcut template: `launcher/Research Assistant.desktop`

Usage:
1) Ensure the launcher script is executable:
   - `chmod +x launcher/start_assistant.sh`
2) Copy the desktop shortcut to your Desktop:
   - `cp "launcher/Research Assistant.desktop" ~/Desktop/`
3) If your project path differs, edit the desktop file to point to the correct location.
4) Double‑click the desktop shortcut to start everything.

## systemd (Optional)
Copy service files to `/etc/systemd/system/` and enable. If your project path differs, update the service files first:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now assistant-bot.service
sudo systemctl enable --now assistant-web.service
```

## Notes
- The system runs only while the computer is on and not sleeping.
- The database is stored in `data/assistant.db` (ignored by Git).

## License
MIT
