import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    base_dir: Path
    data_dir: Path
    db_path: Path
    timezone: str
    telegram_bot_token: str
    telegram_chat_id: str | None
    gemini_api_key: str
    semantic_scholar_api_key: str | None
    thesis_topic: str
    paper_keywords: list[str]
    max_papers_per_day: int
    paper_scan_time: str
    morning_digest_time: str
    web_host: str
    web_port: int
    web_secret_key: str
    log_level: str


def _split_keywords(value: str) -> list[str]:
    return [kw.strip() for kw in value.split(",") if kw.strip()]


def load_config() -> Config:
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = Path(os.getenv("DATA_DIR", base_dir / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = Path(os.getenv("DB_PATH", data_dir / "assistant.db"))

    timezone = os.getenv("TIMEZONE", "Europe/Istanbul")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required")

    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or None
    semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip() or None

    thesis_topic = os.getenv(
        "THESIS_TOPIC",
        "SAR despeckling and vision-language models for remote sensing.",
    )
    paper_keywords = _split_keywords(
        os.getenv(
            "PAPER_KEYWORDS",
            "SAR,synthetic aperture radar,despeckling,vision-language model,remote sensing",
        )
    )
    max_papers_per_day = int(os.getenv("MAX_PAPERS_PER_DAY", "30"))

    paper_scan_time = os.getenv("PAPER_SCAN_TIME", "07:30")
    morning_digest_time = os.getenv("MORNING_DIGEST_TIME", "08:30")

    web_host = os.getenv("WEB_HOST", "0.0.0.0")
    web_port = int(os.getenv("WEB_PORT", "8080"))
    web_secret_key = os.getenv("WEB_SECRET_KEY", "change-me")

    log_level = os.getenv("LOG_LEVEL", "INFO")

    return Config(
        base_dir=base_dir,
        data_dir=data_dir,
        db_path=db_path,
        timezone=timezone,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        gemini_api_key=gemini_api_key,
        semantic_scholar_api_key=semantic_scholar_api_key,
        thesis_topic=thesis_topic,
        paper_keywords=paper_keywords,
        max_papers_per_day=max_papers_per_day,
        paper_scan_time=paper_scan_time,
        morning_digest_time=morning_digest_time,
        web_host=web_host,
        web_port=web_port,
        web_secret_key=web_secret_key,
        log_level=log_level,
    )
