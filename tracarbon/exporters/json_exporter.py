import atexit
import os
from datetime import datetime
from typing import Any

import ujson

from tracarbon.exporters.exporter import Exporter, Metric


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

    async def launch(self, metric: Metric) -> None:
        """
        Launch the Stdout exporter with the metrics.

        :param metric: the metric to send
        :return:
        """
        file_exists = os.path.isfile(self.path)
        with open(self.path, "a+") as file:
            if file_exists:
                file.write(f",{os.linesep}")
            else:
                file.write(f"[{os.linesep}")
            ujson.dump(
                {
                    "timestamp": str(datetime.utcnow()),
                    "metric_name": metric.format_name(
                        metric_prefix_name=self.metric_prefix_name
                    ),
                    "metric_value": await metric.value(),
                    "metric_tags": metric.format_tags(),
                },
                file,
                indent=self.indent,
            )

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        return "JSON"
