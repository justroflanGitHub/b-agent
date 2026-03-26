"""
Browser Agent Logging Configuration

Structured logging with correlation IDs and JSON output.
"""

import logging
import sys
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from contextvars import ContextVar
from functools import wraps
import os


# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return correlation_id.get()


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID in context. Generates new one if not provided."""
    if corr_id is None:
        corr_id = str(uuid.uuid4())[:12]
    correlation_id.set(corr_id)
    return corr_id


def clear_correlation_id():
    """Clear the correlation ID from context."""
    correlation_id.set(None)


class CorrelationIdFilter(logging.Filter):
    """Logging filter to add correlation ID to log records."""
    
    def filter(self, record):
        record.correlation_id = get_correlation_id() or '-'
        return True


class StructuredFormatter(logging.Formatter):
    """
    Structured JSON log formatter.
    
    Outputs logs as JSON objects with consistent structure.
    """
    
    def __init__(self, include_extra: bool = True, pretty: bool = False):
        super().__init__()
        self.include_extra = include_extra
        self.pretty = pretty and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, 'correlation_id', '-'),
        }
        
        # Add location info
        entry["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName
        }
        
        # Add exception info if present
        if record.exc_info:
            entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'pathname', 'process', 'processName', 'relativeCreated',
                    'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                    'message', 'correlation_id'
                }:
                    try:
                        json.dumps(value)  # Check if serializable
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                entry["extra"] = extra_fields
        
        if self.pretty:
            return json.dumps(entry, indent=2, default=str)
        return json.dumps(entry, default=str)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.
    
    Includes colors and correlation IDs.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        # Get correlation ID
        corr_id = getattr(record, 'correlation_id', '-')
        
        # Format timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        # Color level
        color = self.COLORS.get(record.levelname, '')
        level = f"{color}{record.levelname:8}{self.RESET}" if color else record.levelname
        
        # Build message
        parts = [f"[{timestamp}]", f"[{corr_id}]", f"{level}", f"{record.name}:"]
        
        message = record.getMessage()
        parts.append(message)
        
        # Add exception if present
        if record.exc_info:
            parts.append("\n" + self.formatException(record.exc_info))
        
        return " ".join(parts)


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    include_correlation: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging for the browser agent.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON structured logs
        include_correlation: If True, include correlation IDs in logs
        log_file: Optional file path for log output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Choose formatter
    if json_output or os.getenv("LOG_FORMAT", "").lower() == "json":
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()
    
    console_handler.setFormatter(formatter)
    
    # Add correlation filter
    if include_correlation:
        console_handler.addFilter(CorrelationIdFilter())
    
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(StructuredFormatter())  # Always JSON for files
        if include_correlation:
            file_handler.addFilter(CorrelationIdFilter())
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_context(**kwargs):
    """
    Decorator to add extra context to log messages.
    
    Usage:
        @log_context(task_id="123", action="click")
        def my_function():
            logger.info("Doing something")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **func_kwargs):
            logger = get_logger(func.__module__)
            old_factory = logging.getLogRecordFactory()
            
            def record_factory(*factory_args, **factory_kwargs):
                record = old_factory(*factory_args, **factory_kwargs)
                for key, value in kwargs.items():
                    setattr(record, key, value)
                return record
            
            logging.setLogRecordFactory(record_factory)
            try:
                return func(*args, **func_kwargs)
            finally:
                logging.setLogRecordFactory(old_factory)
        
        return wrapper
    return decorator


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds extra context to all messages.
    
    Usage:
        logger = LoggerAdapter(get_logger(__name__), {"task_id": "123"})
        logger.info("Message")  # Will include task_id
    """
    
    def process(self, msg, kwargs):
        # Add extra fields
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra'].update(self.extra)
        return msg, kwargs


# Convenience function to create contextual logger
def get_contextual_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger with persistent context.
    
    Args:
        name: Logger name
        **context: Context fields to add to all log messages
        
    Returns:
        LoggerAdapter with context
    """
    return LoggerAdapter(get_logger(name), context)
