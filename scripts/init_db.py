import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import init_db


def main():
    init_db()
    print("Database initialized.")


if __name__ == "__main__":
    main()
