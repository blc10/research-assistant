import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import init_db
from app.web.app import create_app


def main():
    init_db()
    app = create_app()
    app.run(host=app.config["WEB_HOST"], port=app.config["WEB_PORT"], debug=False)


if __name__ == "__main__":
    main()
