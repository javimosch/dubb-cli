import os


class Config:
    def __init__(self):
        self.port = int(os.getenv("DUBB_PORT", "8080"))
        self.host = os.getenv("DUBB_HOST", "0.0.0.0")
        self.upload_dir = os.getenv("DUBB_UPLOAD_DIR", "/tmp/dubb_uploads")
        self.log_level = os.getenv("DUBB_LOG_LEVEL", "INFO")
