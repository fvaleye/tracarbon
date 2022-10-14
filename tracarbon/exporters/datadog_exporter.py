import os
from typing import Any, List, Optional

from loguru import logger

from tracarbon.exporters.exporter import Exporter, Metric

try:
    from datadog import ThreadStats, initialize

    DATADOG_INSTALLED = True
except ImportError:
    logger.debug("Datadog optional dependency is not installed.")
    DATADOG_INSTALLED = False


if DATADOG_INSTALLED:

    class DatadogExporter(Exporter):
        """
        Datadog exporter for the metrics.
        """

        api_key: Optional[str] = None
        app_key: Optional[str] = None
        stats: Optional[ThreadStats] = None
        disable_buffering: bool = False
        datadog_flush_interval: int = 10

        def __init__(self, **data: Any) -> None:
            """
            Initialize the Datadog Exporter.

            :return:
            """
            super().__init__(**data)
            initialize(
                flush_interval=self.datadog_flush_interval,
                api_key=self.api_key if self.api_key else os.environ["DATADOG_API_KEY"],
                app_key=self.app_key if self.app_key else os.environ["DATADOG_APP_KEY"],
                disable_buffering=self.disable_buffering,
            )
            self.stats = ThreadStats()
            self.stats.start()

        async def launch(self, metric: Metric) -> None:
            """
            Launch the Datadog exporter with the metrics.

            :param metric: the metric to send
            :return:
            """
            metric_value = await metric.value()
            metric_name = metric.format_name(metric_prefix_name=self.metric_prefix_name)
            logger.debug(
                f"Sending metric[{metric_name}] with value [{metric_value}] to Datadog."
            )
            self.stats.gauge(metric_name, metric_value, tags=metric.format_tags())  # type: ignore

        @classmethod
        def get_name(cls) -> str:
            """
            Get the name of the exporter.

            :return: the Exporter's name
            """
            return "Datadog"
