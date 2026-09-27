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
        "private_exists": bool(
            os.getenv("VAPID_PRIVATE_KEY")
        ),
        "private_length": len(
            os.getenv("VAPID_PRIVATE_KEY", "")
        ),
        "public_exists": bool(
            os.getenv("VAPID_PUBLIC_KEY")
        ),
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

    DATABASE_URL = os.getenv(
        "DATABASE_URL"
    )

    if DATABASE_URL:

        # Some PostgreSQL providers may return:
        # postgres://
        #
        # SQLAlchemy uses:
        # postgresql://
        if DATABASE_URL.startswith(
            "postgres://"
        ):

            DATABASE_URL = DATABASE_URL.replace(
                "postgres://",
                "postgresql://",
                1
            )

        SQLALCHEMY_DATABASE_URI = (
            DATABASE_URL
        )

    else:

        # ----------------------------------------------------
        # LOCAL SQLITE DATABASE
        # ----------------------------------------------------

        INSTANCE_DIR = (
            BASE_DIR / "instance"
        )

        INSTANCE_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        SQLALCHEMY_DATABASE_URI = (
            "sqlite:///"
            + str(
                INSTANCE_DIR / "bizflow.db"
            )
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
    # RESEND EMAIL
    #
    # Password-reset emails are sent through the Resend API.
    #
    # RESEND_API_KEY:
    #   Your Resend API key.
    #
    # RESEND_FROM_EMAIL:
    #   The verified sender address.
    #
    # Example for initial testing:
    #
    # RESEND_FROM_EMAIL=onboarding@resend.dev
    #
    # Later, after verifying your own domain:
    #
    # RESEND_FROM_EMAIL=noreply@yourdomain.com
    # ========================================================

    RESEND_API_KEY = os.getenv(
        "RESEND_API_KEY"
    )

    RESEND_FROM_EMAIL = os.getenv(
        "RESEND_FROM_EMAIL",
        "onboarding@resend.dev"
    )
