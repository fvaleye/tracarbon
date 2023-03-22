from loguru import logger

from tracarbon.exporters.exporter import Exporter, MetricGenerator


class StdoutExporter(Exporter):
    """
    Print the metrics to Stdout.
    """

    async def launch(self, metric_generator: MetricGenerator) -> None:
        """
        Launch the Stdout exporter with the metrics.

        :param metric_generator: the metric generator
        """
        async for metric in metric_generator.generate():
            metric_value = await metric.value()
            if metric_value:
                logger.info(
                    f"Metric name[{metric.format_name(metric_prefix_name=self.metric_prefix_name)}], value[{metric_value}], tags{metric.format_tags()}"
                )

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        return "Stdout"
