import os
import sys
from typing import Any

from pydantic import BaseModel


def logger_configuration() -> None:
    """
    Configure the logger format.
    """
    from loguru import logger

    format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <cyan><level>{level: <8}</level></cyan> <level>{message}</level>"
    config = {
        "handlers": [
            {"sink": sys.stderr, "format": format},
        ],
    }
    logger.configure(**config)  # type: ignore


class TracarbonConfiguration(BaseModel):
    """
    The Configuration of Tracarbon.
    """

    api_activated: bool
    metric_prefix_name: str
    log_level: str
    interval_in_seconds: int

    def __init__(self, **data: Any) -> None:
        api_activated = os.environ.get("TRACARBON_API_ACTIVATED", True)
        metric_prefix_name = os.environ.get("TRACARBON_METRIC_PREFIX_NAME", "tracarbon")
        interval_in_seconds = os.environ.get("TRACARBON_INTERVAL_IN_SECONDS", 60)
        log_level = os.environ.get("TRACARBON_LOG_LEVEL", "INFO")
        os.environ["LOGURU_LEVEL"] = log_level
        logger_configuration()
        super().__init__(
            api_activated=api_activated,
            metric_prefix_name=metric_prefix_name,
            log_level=log_level,
            interval_in_seconds=interval_in_seconds,
            **data
        )


tracarbon_configuration = TracarbonConfiguration()
