import os
import sys
from typing import Any
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel


def check_optional_dependency(name: str) -> bool:
    import importlib.util

    from loguru import logger

    try:
        importlib.import_module(name)
    except ImportError:
        logger.debug(f"{name} optional dependency is not installed.")
        return False
    return True


KUBERNETES_INSTALLED = check_optional_dependency(name="kubernetes")
DATADOG_INSTALLED = check_optional_dependency(name="datadog")
PROMETHEUS_INSTALLED = check_optional_dependency(name="prometheus_client")


def logger_configuration(level: str) -> None:
    """
    Configure the logger format.
    """
    from loguru import logger

    format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <cyan><level>{level: <8}</level></cyan> <level>{message}</level>"
    config = {
        "handlers": [
            {"sink": sys.stderr, "format": format, "level": level},
        ],
    }
    logger.configure(**config)  # type: ignore


class TracarbonConfiguration(BaseModel):
    """
    The Configuration of Tracarbon.
    """

    metric_prefix_name: str
    log_level: str
    interval_in_seconds: int
    co2signal_api_key: str
    co2signal_url: str

    def __init__(
        self,
        metric_prefix_name: str = "tracarbon",
        interval_in_seconds: int = 60,
        log_level: str = "INFO",
        co2signal_api_key: str = "",
        co2signal_url: str = "https://api.co2signal.com/v1/latest?countryCode=",
        env_file_path: Optional[str] = None,
        **data: Any,
    ) -> None:
        load_dotenv(env_file_path)
        log_level = os.environ.get("TRACARBON_LOG_LEVEL", log_level)
        logger_configuration(level=log_level)
        super().__init__(
            metric_prefix_name=os.environ.get("TRACARBON_METRIC_PREFIX_NAME", metric_prefix_name),
            log_level=log_level,
            interval_in_seconds=os.environ.get("TRACARBON_INTERVAL_IN_SECONDS", interval_in_seconds),
            co2signal_api_key=os.environ.get("TRACARBON_CO2SIGNAL_API_KEY", co2signal_api_key),
            co2signal_url=os.environ.get("TRACARBON_CO2SIGNAL_URL", co2signal_url),
            **data,
        )
