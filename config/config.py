# config/config.py

import os
from pathlib import Path
from dotenv import load_dotenv

ENV = os.getenv("ENV", "dev")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / "config" / f".{ENV}.env"

load_dotenv(ENV_FILE)


class Config:
    # AWS
    AWS_REGION = os.getenv("AWS_REGION")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Iceberg
    BUCKET_NAME = os.getenv("BUCKET_NAME")
    DATABASE_NAME = os.getenv("GLUE_DATABASE_NAME")
    TABLE_NAME = os.getenv("TABLE_NAME")

    WAREHOUSE_PATH = f"s3://{BUCKET_NAME}/warehouse"

    # Producer
    TARGET_TPS = int(os.getenv("TARGET_TPS", "500"))
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data/transactions")
    ROTATE_SECONDS = int(os.getenv("ROTATE_SECONDS", "60"))
    ROTATE_SIZE_MB = int(os.getenv("ROTATE_SIZE_MB", "64"))
    DURATION_SECONDS = int(os.getenv("DURATION_SECONDS", "0"))

    @classmethod
    def validate(cls):
        assert cls.TARGET_TPS > 0
        assert cls.OUTPUT_DIR
        assert cls.BUCKET_NAME
        assert cls.DATABASE_NAME
        assert cls.TABLE_NAME
