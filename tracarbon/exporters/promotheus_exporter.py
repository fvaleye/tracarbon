import os
from typing import Any, Dict, Optional

from loguru import logger

from tracarbon.exporters.exporter import Exporter, Metric

try:
    import prometheus_client
    from prometheus_client import CollectorRegistry, Gauge, start_http_server

    PROMOTHEUS_INSTALLED = True
except ImportError:
    logger.debug("Promotheus optional dependency is not installed.")
    PROMOTHEUS_INSTALLED = False

if PROMOTHEUS_INSTALLED:

    class PromotheusExporter(Exporter):
        """
        Send the metrics to Promotheus by running an HTTP server for the metrics exposure.
        """

        promotheus_metrics: Dict[str, Gauge] = dict()
        address: Optional[str] = None
        port: Optional[int] = None

        def __init__(self, **data: Any) -> None:
            """
            Initialize the Promotheus Exporter with basic configuration.

            Use
            """
            super().__init__(**data)
            prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
            addr = (
                self.address
                if self.address
                else os.environ.get("PROMOTHEUS_ADDRESS", "localhost")
            )
            port = (
                self.port if self.port else int(os.environ.get("PROMOTHEUS_PORT", 8080))
            )
            start_http_server(
                addr=addr,
                port=port,
            )

        async def launch(self, metric: Metric) -> None:
            """
            Launch the Promotheus exporter with the metrics.

            :param metric: the metric to send
            :return:
            """
            metric_name = metric.format_name(
                metric_prefix_name=self.metric_prefix_name, separator="_"
            )
            if metric_name not in self.promotheus_metrics:
                self.promotheus_metrics[metric_name] = Gauge(
                    metric_name,
                    f"Tracarbon metric {metric_name}",
                    [tag.key for tag in metric.tags],
                )
            metric_value = await metric.value()
            logger.info(
                f"Sending metric[{metric_name}] with value [{metric_value}] to Promoteus."
            )
            self.promotheus_metrics[metric_name].labels(
                *[tag.value for tag in metric.tags]
            ).set(metric_value)

        @classmethod
        def get_name(cls) -> str:
            """
            Get the name of the exporter.

            :return: the Exporter's name
            """
            return "Promotheus"
