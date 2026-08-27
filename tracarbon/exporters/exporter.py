import asyncio
import sys
import time
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

from asyncer import asyncify
from loguru import logger
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import PrivateAttr

from tracarbon.hardwares.energy import EnergyUsageUnit
from tracarbon.hardwares.energy import Power
from tracarbon.hardwares.hardware import HardwareInfo
from tracarbon.locations import Location

_UNITS_OF_POWER = frozenset({EnergyUsageUnit.WATT.value, EnergyUsageUnit.MILLIWATT.value})
_WATT_HOURS = "watt-hours"
# How long a series that stopped reporting is remembered, so that the series of a container which
# has gone do not accumulate for the life of the process.
_SERIES_ARE_FORGOTTEN_AFTER_SECONDS = 3600


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
    value: Callable[[], Awaitable[float | None]]
    tags: List[Tag] = Field(default_factory=list)

    def format_name(self, metric_prefix_name: str | None = None, separator: str = ".") -> str:
        """
        Format the name of the metric with a prefix and separator.

        :param metric_prefix_name: the prefix to insert before the separator and the name.
        :param separator: the separator to use between the prefix and the name.
        """
        if metric_prefix_name:
            return f"{metric_prefix_name}{separator}{self.name}"
        return self.name

    def unit(self) -> str | None:
        """
        Get the unit the values of this metric are reported in.

        :return: the unit, or None if the metric declares none
        """
        return next((tag.value for tag in self.tags if tag.key == "units"), None)

    def format_tags(self, separator: str = ":") -> List[str]:
        """
        Format tags with a separator.

        :param separator: the separator to insert between the key and value.
        """
        return [f"{tag.key}{separator}{tag.value}" for tag in self.tags]


class MetricReport(BaseModel):
    """
    MetricReport is a report of the generated metrics.

    A metric reported in watts is power, so it is integrated over the interval it was measured on
    and totalled as the watt-hours total_unit carries. Every series sharing a metric name is
    integrated on its own interval.
    """

    exporter_name: str
    metric: "Metric"
    average_interval_in_seconds: float | None = None
    last_report_time: datetime | None = None
    total: float = 0.0
    total_unit: str | None = None
    average: float = 0.0
    minimum: float = sys.float_info.max
    maximum: float = 0.0
    call_count: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _measured_at_by_series: Dict[str, float] = PrivateAttr(default_factory=dict)
    _interval_count: int = PrivateAttr(default=0)

    def _record_the_interval_of(self, series: str, measured_at: float) -> None:
        """
        Add the interval this series just spanned to the average of the intervals seen, measured
        on the series rather than on the name it shares.

        :param series: the series being reported
        :param measured_at: the time of the reading being recorded
        """
        measured_before = self._measured_at_by_series.get(series)
        if measured_before is None:
            return
        interval = measured_at - measured_before
        self._interval_count += 1
        average = self.average_interval_in_seconds or 0.0
        self.average_interval_in_seconds = average + (interval - average) / self._interval_count

    def _forget_the_series_that_stopped_reporting(self, measured_at: float) -> None:
        """
        Drop the series that have not reported for long enough to be gone, since a container that
        restarts comes back under a new key and keeping every key ever seen has no ceiling. One
        that comes back opens a new window rather than measuring the whole absence.

        :param measured_at: the time of the reading being recorded
        """
        forgotten_before = measured_at - _SERIES_ARE_FORGOTTEN_AFTER_SECONDS
        for series, last_measured_at in list(self._measured_at_by_series.items()):
            if last_measured_at < forgotten_before:
                del self._measured_at_by_series[series]

    def accumulate(self, metric: "Metric", value: float, measured_at: float) -> None:
        """
        Add one reported value to the running total, the average and the bounds.

        :param metric: the metric the value was reported for
        :param value: the reported value
        :param measured_at: when it was reported, on a clock that only moves forward
        """
        series = ",".join(metric.format_tags())
        unit = metric.unit()
        if unit in _UNITS_OF_POWER:
            watts = value / Power.MILLIWATTS_TO_WATT_FACTOR if unit == EnergyUsageUnit.MILLIWATT.value else value
            measured_before = self._measured_at_by_series.get(series)
            if measured_before is not None:
                self.total += Power.watt_hours_from_watts_over(watts=watts, seconds=measured_at - measured_before)
            self.total_unit = _WATT_HOURS
        else:
            self.total += value
            self.total_unit = unit
        self._record_the_interval_of(series=series, measured_at=measured_at)
        self._measured_at_by_series[series] = measured_at

        self.call_count += 1
        self.average += (value - self.average) / self.call_count
        if value < self.minimum:
            self.minimum = value
        if value > self.maximum:
            self.maximum = value


class MetricGenerator(BaseModel):
    """
    MetricGenerator generates metrics for the Exporter.
    """

    metrics: List[Metric]
    platform: str = HardwareInfo.get_platform()
    location: Location | None = None

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate a metric.
        """
        for metric in self.metrics:
            yield metric


class Exporter(BaseModel, metaclass=ABCMeta):
    """The Exporter interface."""

    metric_generators: List[MetricGenerator]
    event: Event | None = None
    stopped: bool = False
    metric_prefix_name: str | None = None
    metric_report: Dict[str, MetricReport] = Field(default_factory=dict)
    _timer: Timer | None = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
                self._timer = timer
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
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    async def _launch_all(self) -> None:
        """
        Launch the exporter with all the metric generators.
        """
        cycle_started_at = time.monotonic()
        for metric_generator in self.metric_generators:
            logger.debug(f"Running MetricGenerator[{metric_generator}].")
            await self.launch(metric_generator=metric_generator)
        for metric_report in self.metric_report.values():
            metric_report._forget_the_series_that_stopped_reporting(measured_at=cycle_started_at)

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
            metric_report.accumulate(metric=metric, value=value, measured_at=time.monotonic())
            metric_report.last_report_time = now
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
