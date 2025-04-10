import logging
from .handler import GoogleCloudHandler
from google.cloud.logging_v2.handlers import setup_logging
import os


def init():
import structlog


def init():
    logging.getLogger().handlers.clear()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    handler = GoogleCloudHandler(project_id=project_id)
    setup_logging(handler)


def get_logger(name):
    return logging.getLogger(name)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name) -> logging.Logger:
    return structlog.get_logger(name=name)
