import os
from typing import Any
from typing import Optional

from loguru import logger

from tracarbon.conf import DATADOG_INSTALLED
from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import MetricGenerator

if DATADOG_INSTALLED:
    from datadog import ThreadStats
    from datadog import initialize

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

        async def launch(self, metric_generator: MetricGenerator) -> None:
            """
            Launch the Datadog exporter with the metrics.

            :param metric_generator: the metric generators
            :return:
            """
            async for metric in metric_generator.generate():
                metric_value = await metric.value()
                if metric_value:
                    await self.add_metric_to_report(metric=metric, value=metric_value)
                    metric_name = metric.format_name(metric_prefix_name=self.metric_prefix_name)
                    logger.info(
                        f"Sending metric[{metric_name}] with value [{metric_value}] and tags{metric.format_tags()} to Datadog."
                    )
                    self.stats.gauge(metric_name, metric_value, tags=metric.format_tags())

        @classmethod
        def get_name(cls) -> str:
            """
            Get the name of the exporter.

            :return: the Exporter's name
            """
            return "Datadog"
