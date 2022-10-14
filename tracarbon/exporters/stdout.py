from loguru import logger

from tracarbon.exporters.exporter import Exporter, Metric


class StdoutExporter(Exporter):
    """
    Print the metrics to Stdout.
    """

    async def launch(self, metric: Metric) -> None:
        """
        Launch the Stdout exporter with the metrics.

        :param metric: the metric to send
        """
        logger.info(
            f"Metric name[{metric.format_name(metric_prefix_name=self.metric_prefix_name)}], value[{await metric.value()}], tags[{metric.format_tags()}]"
        )

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        return "Stdout"
