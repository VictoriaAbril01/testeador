"""Build a database URL without hard-coding or logging credentials."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_database_url() -> URL:
    load_dotenv(PROJECT_ROOT / ".env")
    if explicit_url := os.getenv("DATABASE_URL"):
        url = make_url(explicit_url)
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return url

    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ValueError("POSTGRES_PASSWORD is required in the environment or .env")

    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "testlab"),
        password=password,
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "testlab"),
    )
