import logging
import logging.config
import sys
import os
import json
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for production logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_obj.update(record.extra_fields)
            
        return json.dumps(log_obj)


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration based on environment"""
    
    environment = os.getenv("ENVIRONMENT", "development").lower()
    log_level = os.getenv("LOG_LEVEL", "DEBUG" if environment == "development" else "INFO")
    
    if environment == "production":
        # Production: JSON format for log aggregation
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JSONFormatter,
                    "datefmt": "%Y-%m-%dT%H:%M:%SZ"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "json",
                    "level": log_level
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["console"]
            },
            "loggers": {
                "app": {
                    "level": log_level,
                    "propagate": True
                },
                "uvicorn": {
                    "level": "INFO",
                    "propagate": True
                }
            }
        }
    else:
        # Development: Human-readable format
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "detailed",
                    "level": log_level
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["console"]
            },
            "loggers": {
                "app": {
                    "level": log_level,
                    "propagate": True
                },
                "uvicorn": {
                    "level": "INFO",
                    "propagate": True
                }
            }
        }


def setup_logging():
    """Setup logging configuration"""
    config = get_logging_config()
    logging.config.dictConfig(config)
    
    # Get root logger and log startup message
    logger = logging.getLogger("app")
    environment = os.getenv("ENVIRONMENT", "development")
    logger.info(f"Logging initialized for {environment} environment")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name"""
    return logging.getLogger(f"app.{name}")