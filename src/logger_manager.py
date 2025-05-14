import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import time
from datetime import datetime
import shutil


class LoggerManager:
    def __init__(self, log_dir="logs", max_file_size=1 * 1024 * 1024, backup_count=5):
        self.base_log_dir = log_dir
        self.max_file_size = max_file_size
        self.backup_count = backup_count

        # Create today's log directory (e.g., logs/2025-05-01/)
        self.today_str = datetime.now().strftime('%Y-%m-%d')
        self.log_dir = os.path.join(self.base_log_dir, self.today_str)
        self.backup_dir = os.path.join(self.log_dir, "backup")
        os.makedirs(self.backup_dir, exist_ok=True)

        # Define main log file path
        self.log_file = os.path.join(self.log_dir, "main.log")

        # Move existing main.log to backup (with timestamp)
        self._archive_old_log_if_exists()

        # Setup logging
        self.setup_logging()

    def _archive_old_log_if_exists(self):
        if os.path.exists(self.log_file):
            timestamp = time.strftime("%H%M%S")
            archived_file = os.path.join(self.backup_dir, f"main_{timestamp}.log")
            shutil.move(self.log_file, archived_file)

    def setup_logging(self):
        self.logger = logging.getLogger("LoggerManager")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # Clear existing handlers to prevent duplicate logs

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # File handler (includes traceback)
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Console handler (excludes traceback)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def write(self, message, error=False, exc=None):
        if error and exc:
            self.logger.error(message, exc_info=exc)
        else:
            self.logger.info(message)

    def close(self):
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)