import os

from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# VAPID DEBUG
# ============================================================

print(
    "VAPID DEBUG:",
    {
        "private_exists": bool(os.getenv("VAPID_PRIVATE_KEY")),
        "private_length": len(
            os.getenv("VAPID_PRIVATE_KEY", "")
        ),
        "public_exists": bool(os.getenv("VAPID_PUBLIC_KEY")),
        "public_length": len(
            os.getenv("VAPID_PUBLIC_KEY", "")
        ),
        "subject_exists": bool(
            os.getenv("VAPID_SUBJECT")
        ),
    }
)


class Config:

    # ========================================================
    # FLASK
    # ========================================================

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "fallback-development-secret-key"
    )

    # ========================================================
    # DATABASE
    #
    # LOCAL:
    #   Uses SQLite automatically when DATABASE_URL is not set.
    #
    # RENDER:
    #   Uses PostgreSQL automatically when DATABASE_URL
    #   is provided by Render.
    # ========================================================

    DATABASE_URL = os.getenv("DATABASE_URL")

    if DATABASE_URL:

        # Some PostgreSQL providers may return:
        # postgres://
        #
        # SQLAlchemy uses:
        # postgresql://
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace(
                "postgres://",
                "postgresql://",
                1
            )

        SQLALCHEMY_DATABASE_URI = DATABASE_URL

    else:

        # ----------------------------------------------------
        # LOCAL SQLITE DATABASE
        # ----------------------------------------------------

        INSTANCE_DIR = BASE_DIR / "instance"

        INSTANCE_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        SQLALCHEMY_DATABASE_URI = (
            "sqlite:///"
            + str(INSTANCE_DIR / "bizflow.db")
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Prevent stale database connections from causing
    # connection errors, especially on hosted PostgreSQL.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # ========================================================
    # VAPID / WEB PUSH
    # ========================================================

    VAPID_PRIVATE_KEY = os.getenv(
        "VAPID_PRIVATE_KEY"
    )

    VAPID_PUBLIC_KEY = os.getenv(
        "VAPID_PUBLIC_KEY"
    )

    VAPID_SUBJECT = os.getenv(
        "VAPID_SUBJECT"
    )

    # ========================================================
    # MAIL
    # ========================================================

    MAIL_SERVER = os.getenv(
        "MAIL_SERVER",
        "smtp.gmail.com"
    )

    MAIL_PORT = int(
        os.getenv(
            "MAIL_PORT",
            "587"
        )
    )

    MAIL_USE_TLS = (
        os.getenv(
            "MAIL_USE_TLS",
            "true"
        ).lower()
        == "true"
    )

    MAIL_USE_SSL = (
        os.getenv(
            "MAIL_USE_SSL",
            "false"
        ).lower()
        == "true"
    )

    MAIL_USERNAME = os.getenv(
        "MAIL_USERNAME"
    )

    MAIL_PASSWORD = os.getenv(
        "MAIL_PASSWORD"
    )

    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER"
    )