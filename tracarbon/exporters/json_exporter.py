import atexit
import os
from datetime import datetime
from datetime import timezone
from typing import Any

import aiofiles
import orjson

from tracarbon.exporters.exporter import Exporter
from tracarbon.exporters.exporter import MetricGenerator


class JSONExporter(Exporter):
    """
    Write the metrics to a local JSON file.
    """

    path: str = ""
    indent: int = 4

    def __init__(self, **data: Any) -> None:
        # Register flush at exit
        if "path" not in data or not data.get("path"):
            data["path"] = datetime.now().strftime("tracarbon_export_%d_%m_%Y.json")
        super().__init__(**data)
        atexit.register(self.flush)

    def _strip_trailing_closing_bracket(self) -> None:
        """
        If the JSON file ends with a closing bracket, truncate it so we can append
        new elements and keep a valid JSON array across multiple runs.
        """
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "rb+") as file:
                file.seek(0, os.SEEK_END)
                end = file.tell()
                # Move backwards to find last non-whitespace char
                while end > 0:
                    end -= 1
                    file.seek(end)
                    ch = file.read(1)
                    if ch not in b" \t\r\n":
                        break
                if ch == b"]":
                    file.truncate(end)
        except Exception as exc:
            # Log and continue; we can still write a fresh array
            from loguru import logger

            logger.debug(f"JSONExporter: could not strip trailing bracket for {self.path}: {exc}")

    def flush(self) -> None:
        """
        Close the JSON array if needed by appending a closing bracket.
        """
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "rb+") as file:
                file.seek(0, os.SEEK_END)
                size = file.tell()
                if size == 0:
                    # Write empty array
                    file.write(b"[]")
                    return
                # Check if already closed
                pos = size
                last = None
                while pos > 0:
                    pos -= 1
                    file.seek(pos)
                    ch = file.read(1)
                    if ch not in b" \t\r\n":
                        last = ch
                        break
                if last != b"]":
                    file.write(b"\n]")
        except Exception as exc:
            from loguru import logger

            logger.debug(f"JSONExporter: flush failed for {self.path}: {exc}")

    async def launch(self, metric_generator: MetricGenerator) -> None:
        """
        Launch the Stdout exporter with the metrics.

        :param metric_generator: the metric generator
        """
        # Ensure we can append to an existing closed array from a previous run
        self._strip_trailing_closing_bracket()
        async for metric in metric_generator.generate():
            metric_value = await metric.value()
            if metric_value is not None:
                await self.add_metric_to_report(metric=metric, value=metric_value)
                file_exists = os.path.isfile(self.path)
                async with aiofiles.open(self.path, "a+") as file:
                    if file_exists and os.path.getsize(self.path) > 0:
                        await file.write(f",{os.linesep}")
                    else:
                        await file.write(f"[{os.linesep}")
                    option = orjson.OPT_INDENT_2 if self.indent >= 2 else 0
                    json_bytes = orjson.dumps(
                        {
                            "timestamp": str(datetime.now(timezone.utc)),
                            "metric_name": metric.format_name(metric_prefix_name=self.metric_prefix_name),
                            "metric_value": metric_value,
                            "metric_tags": metric.format_tags(),
                        },
                        option=option,
                    )
                    await file.write(json_bytes.decode("utf-8"))

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        return "JSON"
