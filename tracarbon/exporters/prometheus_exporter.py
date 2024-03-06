import os
from typing import Any
from typing import Dict
from typing import Optional

from loguru import logger

from tracarbon.conf import PROMETHEUS_INSTALLED
from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import MetricGenerator

if PROMETHEUS_INSTALLED:
    import prometheus_client
    from prometheus_client import Gauge
    from prometheus_client import start_http_server

    class PrometheusExporter(Exporter):
        """
        Send the metrics to Prometheus by running an HTTP server for the metrics exposure.
        """

        prometheus_metrics: Dict[str, Gauge] = dict()
        address: Optional[str] = None
        port: Optional[int] = None

        def __init__(self, **data: Any) -> None:
            super().__init__(**data)
            prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
            addr = self.address if self.address else os.environ.get("PROMETHEUS_ADDRESS", "::")
            port = self.port if self.port else int(os.environ.get("PROMETHEUS_PORT", 8081))
            start_http_server(
                addr=addr,
                port=port,
            )

        async def launch(self, metric_generator: MetricGenerator) -> None:
            """
            Launch the Prometheus exporter with the metrics.

            :param metric_generator: the metric generator
            """
            async for metric in metric_generator.generate():
                metric_name = metric.format_name(metric_prefix_name=self.metric_prefix_name, separator="_")
                if metric_name not in self.prometheus_metrics:
                    self.prometheus_metrics[metric_name] = Gauge(
                        metric_name,
                        f"Tracarbon metric {metric_name}",
                        [tag.key for tag in metric.tags],
                    )
                metric_value = await metric.value()
                if metric_value:
                    await self.add_metric_to_report(metric=metric, value=metric_value)
                    logger.info(
                        f"Sending metric[{metric_name}] with value [{metric_value}] and labels{metric.format_tags()} to Prometheus."
                    )
                    self.prometheus_metrics[metric_name].labels(*[tag.value for tag in metric.tags]).set(metric_value)

        @classmethod
        def get_name(cls) -> str:
            """
            Get the name of the exporter.

            :return: the Exporter's name
            """
            return "Prometheus"
