import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import init_db
from app.services.telegram_bot import build_application


def main():
    init_db()
    app = build_application()
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
