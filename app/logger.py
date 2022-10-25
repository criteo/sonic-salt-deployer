"""Logger helper."""
import logging
import logging.config

from app.settings import CONF

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"format_handler": {"format": "%(levelname)s - %(name)s: %(message)s"}},
    "handlers": {
        "stream_handler": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "format_handler",
        }
    },
    "loggers": {
        "": {"level": "INFO", "handlers": ["stream_handler"], "propagate": "false"},
        "asyncssh": {"level": "ERROR"},
    },
}


def get_logger(name: str) -> "logging.Logger":
    """Provide already configured logger."""
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(name.split(".").pop())
    logger.setLevel(CONF.log_level)
    return logger
