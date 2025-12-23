import logging, sys, structlog
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    # Create a file handler for rotational logging
    file_handler = RotatingFileHandler(
        "app.log", 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s]{%(filename)s %(funcName)s:%(lineno)d %(threadName)s} %(levelname)s - %(message)s"
    ))

    # Configure standard logging
    logging.basicConfig(
        format="[%(asctime)s]{%(filename)s %(funcName)s:%(lineno)d %(threadName)s} %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(sys.stdout),
            file_handler
        ]
    )

    # Configure structlog to wrap standard logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )