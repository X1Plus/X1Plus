import logging
from logging.handlers import RotatingFileHandler
import atexit

class CustomLogger:
    def __init__(self, name, filename, maxBytes=1048576, backupCount=5):
        """
        Initializes a custom logger with a RotatingFileHandler.

        Parameters:
        - name: The name of the logger.
        - filename: Path to the log file.
        - maxBytes: Maximum file size before rotating (default is 1MB).
        - backupCount: Number of backup files to keep (default is 5).
        """
        self.logger = logging.getLogger(name)
        if not self.logger.hasHandlers():
            formatter = logging.Formatter("%(asctime)s - %(message)s")
            handler = RotatingFileHandler(filename, maxBytes=maxBytes, backupCount=backupCount)
            handler.setFormatter(formatter)
            self.logger.setLevel(logging.INFO)
            self.logger.addHandler(handler)
            atexit.register(self.removeHandler, handler)

    def removeHandler(self, handler):
        """
        Removes a handler from the logger and closes it. Intended to be called at exit.
        """
        self.logger.removeHandler(handler)
        handler.close()

    def info(self, message):
        """
        Logs an INFO level message.
        """
        self.logger.info(message)

    def debug(self, message):
        """
        Logs a DEBUG level message.
        """
        self.logger.debug(message)

    def error(self, message):
        """
        Logs an ERROR level message.
        """
        self.logger.error(message)

# Usage:
# exampleLog = CustomLogger("exampleLogger", "/tmp/example.log", 1000000, 3)
# exampleLog.info("This is a test log message.")
