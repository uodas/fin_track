# src/config.py
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_folder: str = "database"
    db_name: str = "finance.db"
    input_folder: str = "input"
    log_folder: str = "log"
    log_file: str = "app.log"
    config_file: str = "config.yaml"
    google_service_account: str = "service_account.json"

    model_name: str = "all-MiniLM-L6-v2"
    model_cache: str = "model_cache"

    debug_mode: bool = False
    pythonpath: str = "."

    @property
    def db_path(self) -> str:
        return os.path.join(self.db_folder, self.db_name)

    @property
    def log_path(self) -> str:
        return os.path.join(self.log_folder, self.log_file)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
DB_PATH = settings.db_path
LOG_PATH = settings.log_path
INPUT_FOLDER = settings.input_folder
MODEL_NAME = settings.model_name
MODEL_CACHE = settings.model_cache
GOOGLE_SERVICE_ACCOUNT = settings.google_service_account
CONFIG_FILE = settings.config_file
