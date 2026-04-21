"""
Logging configuration for Internet Archive Concert Tools.

Provides consistent logging across all modules with configurable verbosity.
"""

import logging
import sys
from typing import Optional

from ia_concert_tools.config import Config


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if sys.stderr.isatty():
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


def setup_logging(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        verbose: Enable debug-level logging
        quiet: Suppress info messages, show only warnings and errors
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("ia_concert_tools")
    
    # Determine log level
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    
    # Create formatter
    if sys.stderr.isatty():
        formatter = ColoredFormatter(
            "%(levelname)s: %(message)s",
            datefmt=Config.LOG_DATE_FORMAT
        )
    else:
        formatter = logging.Formatter(
            "%(levelname)s: %(message)s",
            datefmt=Config.LOG_DATE_FORMAT
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Don't propagate to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (defaults to root ia_concert_tools logger)
        
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"ia_concert_tools.{name}")
    return logging.getLogger("ia_concert_tools")
