import os
import sys
from typing import Any

from dotenv import find_dotenv
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic import Field


def check_optional_dependency(name: str) -> bool:
    import importlib.util

    try:
        importlib.import_module(name)
    except ImportError:
        return False
    return True


KUBERNETES_INSTALLED = check_optional_dependency(name="kubernetes")
DATADOG_INSTALLED = check_optional_dependency(name="datadog")
PROMETHEUS_INSTALLED = check_optional_dependency(name="prometheus_client")


_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <cyan><level>{level: <8}</level></cyan> <level>{message}</level>"
)


def logger_configuration(level: str) -> None:
    """
    Replace every loguru handler with the Tracarbon one.

    :param level: the minimum level of the displayed logs
    """
    from loguru import logger

    logger.configure(handlers=[{"sink": sys.stderr, "format": _LOG_FORMAT, "level": level, "diagnose": False}])


class TracarbonConfiguration(BaseModel):
    """
    The Configuration of Tracarbon.
    """

    metric_prefix_name: str
    log_level: str
    interval_in_seconds: int
    co2signal_api_key: str = Field(repr=False)
    co2signal_url: str
    emission_factor_type: str

    def __init__(
        self,
        metric_prefix_name: str = "tracarbon",
        interval_in_seconds: int = 60,
        log_level: str = "INFO",
        co2signal_api_key: str = "",
        co2signal_url: str = "https://api.electricitymaps.com/v4/carbon-intensity/latest",
        emission_factor_type: str = "lifecycle",
        env_file_path: str | None = None,
        **data: Any,
    ) -> None:
        load_dotenv(env_file_path or find_dotenv(usecwd=True))
        super().__init__(
            metric_prefix_name=os.environ.get("TRACARBON_METRIC_PREFIX_NAME", metric_prefix_name),
            log_level=os.environ.get("TRACARBON_LOG_LEVEL", log_level),
            interval_in_seconds=os.environ.get("TRACARBON_INTERVAL_IN_SECONDS", interval_in_seconds),
            co2signal_api_key=os.environ.get("TRACARBON_CO2SIGNAL_API_KEY", co2signal_api_key),
            co2signal_url=os.environ.get("TRACARBON_CO2SIGNAL_URL", co2signal_url),
            emission_factor_type=os.environ.get("TRACARBON_EMISSION_FACTOR_TYPE", emission_factor_type),
            **data,
        )
