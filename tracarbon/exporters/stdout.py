from loguru import logger

from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import MetricGenerator


class StdoutExporter(Exporter):
    """
    Print the metrics to Stdout.
    """

    async def launch(self, metric_generator: MetricGenerator) -> None:
        """
        Launch the Stdout exporter with the metrics.

        :param metric_generator: the metric generator
        """
        try:
            async for metric in metric_generator.generate():
                try:
                    metric_value = await metric.value()
                    logger.debug(f"Generated metric '{metric.name}' with value: {metric_value}")

                    if metric_value is not None:
                        await self.add_metric_to_report(metric=metric, value=metric_value)
                        logger.info(
                            f"Metric name[{metric.format_name(metric_prefix_name=self.metric_prefix_name)}], value[{metric_value}], tags{metric.format_tags()}"
                        )
                    else:
                        logger.debug(f"Skipping metric '{metric.name}' with None value")
                except Exception as e:
                    logger.error(f"Error processing metric '{metric.name}': {e}")
        except Exception as e:
            logger.error(f"Error in StdoutExporter.launch: {e}")

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        return "Stdout"
