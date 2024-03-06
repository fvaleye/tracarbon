import atexit
import os
from datetime import datetime
from typing import Any

import aiofiles
import ujson

from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import MetricGenerator


class JSONExporter(Exporter):
    """
    Write the metrics to a local JSON file.
    """

    path: str = datetime.now().strftime(f"tracarbon_export_%d_%m_%Y.json")
    indent: int = 4

    def __init__(self, **data: Any) -> None:
        # Register flush at exit
        super().__init__(**data)
        atexit.register(self.flush)

    def flush(self) -> None:
        """
        Flush the file and add the closing bracket.
        """
        with open(self.path, "a+") as file:
            file.write(f"{os.linesep}]")

    async def launch(self, metric_generator: MetricGenerator) -> None:
        """
        Launch the Stdout exporter with the metrics.

        :param metric_generator: the metric generator
        """
        async for metric in metric_generator.generate():
            metric_value = await metric.value()
            if metric_value:
                await self.add_metric_to_report(metric=metric, value=metric_value)
                file_exists = os.path.isfile(self.path)
                async with aiofiles.open(self.path, "a+") as file:
                    if file_exists:
                        await file.write(f",{os.linesep}")
                    else:
                        await file.write(f"[{os.linesep}")
                    await file.write(
                        ujson.dumps(
                            {
                                "timestamp": str(datetime.utcnow()),
                                "metric_name": metric.format_name(metric_prefix_name=self.metric_prefix_name),
                                "metric_value": metric_value,
                                "metric_tags": metric.format_tags(),
                            },
                            indent=self.indent,
                        )
                    )

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        return "JSON"
