import logging
import os
from datetime import datetime
from utils import ensure_directory_exists

class Logger:
    def __init__(self, logs_dir, domain):
        self.logs_dir = logs_dir
        self.domain = domain
        self.configure_logging()

    def configure_logging(self):
        """Configure logging with UTF-8 encoding."""
        log_file_name = self.get_log_file_name(self.domain, self.logs_dir)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file_name, encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )

    def log_info(self, message):
        logging.info(message)

    def log_warning(self, message):
        logging.warning(message)

    def log_error(self, message):
        logging.error(message)

    def get_log_file_name(self, domain, logs_dir):
        """Generate the log filename based on the domain and current datetime, and save it in the specified logs directory."""
        # Ensure the logs directory exists
        ensure_directory_exists(logs_dir)

        # Get the current datetime in a formatted string (e.g., 20231015143022)
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

        # Include the domain and datetime in the log filename
        return os.path.join(logs_dir, f"crawler_{domain}_{current_datetime}.log")
