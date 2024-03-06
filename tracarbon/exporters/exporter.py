import asyncio
import sys
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from threading import Event
from threading import Timer
from typing import AsyncGenerator
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from asyncer import asyncify
from loguru import logger
from pydantic import BaseModel

from tracarbon.hardwares.hardware import HardwareInfo
from tracarbon.locations import Location


class Tag(BaseModel):
    """
    Tag for a metric.
    """

    key: str
    value: str


class Metric(BaseModel):
    """
    Global metric to use for the exporters.
    """

    name: str
    value: Callable[[], Awaitable[float]]
    tags: List[Tag] = list()

    def format_name(self, metric_prefix_name: Optional[str] = None, separator: str = ".") -> str:
        """
        Format the name of the metric with a prefix and separator.

        :param metric_prefix_name: the prefix to insert before the separator and the name.
        :param separator: the separator to use between the prefix and the name.
        """
        if metric_prefix_name:
            return f"{metric_prefix_name}{separator}{self.name}"
        return self.name

    def format_tags(self, separator: str = ":") -> List[str]:
        """
        Format tags with a separator.

        :param separator: the separator to insert between the key and value.
        """
        return [f"{tag.key}{separator}{tag.value}" for tag in self.tags]


class MetricReport(BaseModel):
    """
    MetricReport is a report of the generated metrics.
    """

    exporter_name: str
    metric: "Metric"
    average_interval_in_seconds: Optional[float] = None
    last_report_time: Optional[datetime] = None
    total: float = 0.0
    average: float = 0.0
    minimum: float = sys.float_info.max
    maximum: float = 0.0
    call_count: int = 0

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class MetricGenerator(BaseModel):
    """
    MetricGenerator generates metrics for the Exporter.
    """

    metrics: List[Metric]
    platform: str = HardwareInfo.get_platform()
    location: Optional[Location] = None

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate a metric.
        """
        for metric in self.metrics:
            yield metric


class Exporter(BaseModel, metaclass=ABCMeta):
    """The Exporter interface."""

    metric_generators: List[MetricGenerator]
    event: Optional[Event] = None
    stopped: bool = False
    metric_prefix_name: Optional[str] = None
    metric_report: Dict[str, MetricReport] = dict()

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    @abstractmethod
    async def launch(self, metric_generator: "MetricGenerator") -> None:
        """
        Launch the exporter.
        Add the metric generator to the metric reporter.

        :param metric_generator: the metric generator
        """
        pass

    def start(self, interval_in_seconds: int) -> None:
        """
        Start the exporter and a dedicated timer configured with the configured timeout.

        :param: interval_in_seconds: the interval for the timer
        """
        self.stopped = False
        if not self.event:
            self.event = Event()

        def _run() -> None:
            asyncio.run(self._launch_all())
            if self.event and not self.stopped and not self.event.is_set():
                timer = Timer(interval_in_seconds, _run, [])
                timer.daemon = True
                timer.start()

        self.metric_report = dict()
        _run()

    def stop(self) -> None:
        """
        Stop the explorer and the associated timer.

        :return:
        """
        self.stopped = True
        if self.event:
            self.event.set()

    async def _launch_all(self) -> None:
        """
        Launch the exporter with all the metric generators.
        """
        for metric_generator in self.metric_generators:
            logger.debug(f"Running MetricGenerator[{metric_generator}].")
            await self.launch(metric_generator=metric_generator)

    async def add_metric_to_report(self, metric: "Metric", value: float) -> "MetricReport":
        """
        Add the generated metric to the report asynchronously.

        :param metric: the metric to add
        :param value: the metric value to add
        :return:
        """

        def add_metric_to_report() -> MetricReport:
            if metric.name not in self.metric_report:
                self.metric_report[metric.name] = MetricReport(exporter_name=self.get_name(), metric=metric)
            metric_report = self.metric_report[metric.name]
            now = datetime.now()
            if metric_report.last_report_time:
                time_difference_in_s = (now - metric_report.last_report_time).total_seconds()
                metric_report.average_interval_in_seconds = (
                    time_difference_in_s
                    if not metric_report.average_interval_in_seconds
                    else (metric_report.average_interval_in_seconds + time_difference_in_s) / 2
                )

            metric_report.last_report_time = now
            metric_report.total += value
            metric_report.call_count += 1
            metric_report.average = metric_report.total / metric_report.call_count
            if value < metric_report.minimum:
                metric_report.minimum = value
            if value > metric_report.maximum:
                metric_report.maximum = value
            return metric_report

        return await asyncify(add_metric_to_report)()

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        pass
