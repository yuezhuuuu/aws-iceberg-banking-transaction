"""local producer configuration - no AWS dependencies"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """local producer configuration - no AWS dependencies""" 
    
    # producer configuration
    TARGET_TPS = int(os.getenv("TARGET_TPS", "500"))  # 每秒500笔
    
    # output configuration
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data/transactions")
    
    # file rotation configuration (simulate Firehose batching)
    ROTATE_SECONDS = int(os.getenv("ROTATE_SECONDS", "60"))   # 每60秒轮转
    ROTATE_SIZE_MB = int(os.getenv("ROTATE_SIZE_MB", "64"))    # 或每64MB轮转
    DURATION_SECONDS = int(os.getenv("DURATION_SECONDS", "0"))
    @classmethod
    def validate(cls):
        """validate configuration values"""
        assert cls.TARGET_TPS > 0, "TARGET_TPS must be positive"
        assert cls.OUTPUT_DIR, "OUTPUT_DIR is required"