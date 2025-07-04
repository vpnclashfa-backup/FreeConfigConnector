import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(log_file_path: str):
    """
    Sets up logging to capture WARNING and ERROR messages to a specific file.
    All other log messages (INFO, DEBUG) will be ignored by this handler.
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Set overall minimum level to INFO, but handlers can override this.

    # Ensure the directory for the log file exists
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # File handler for errors and warnings only
    # Rotates log file after 1MB, keeps 1 backup file.
    file_handler = RotatingFileHandler(
        log_file_path, 
        maxBytes=1024 * 1024, # 1 MB
        backupCount=1,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.WARNING) # Only log WARNINGs and ERRORs to this file
    
    # Formatter for the log file
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add the handler to the logger
    logger.addHandler(file_handler)

    # Optional: If you also want to keep console output for INFO/DEBUG during development,
    # you can configure a separate console handler. Otherwise, the default console output
    # will be minimal due to higher level of file_handler.
    # For GitHub Actions, often console output is the primary debug.
    # Let's keep a basic console handler that outputs INFO and higher,
    # but actual errors will be in the file.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO) 
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    print(f"Logging configured. Warnings and Errors will be saved to {log_file_path}")