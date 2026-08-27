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
# Long enough that no reporting interval reaches it, short enough that the series of a container
# which has gone do not accumulate for the life of the process.
_SERIES_ARE_FORGOTTEN_AFTER_SECONDS = 3600
# What a reporting interval longer than that floor is measured against instead, so that the
# horizon stays ahead of the interval rather than closing in on it.
_SERIES_ARE_FORGOTTEN_AFTER_INTERVALS = 4


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
        for tag in self.tags:
            if tag.key == "units":
                return tag.value
        return None

    def format_tags(self, separator: str = ":") -> List[str]:
        """
        Format tags with a separator.

        :param separator: the separator to insert between the key and value.
        """
        return [f"{tag.key}{separator}{tag.value}" for tag in self.tags]


class MetricReport(BaseModel):
    """
    MetricReport is a report of the generated metrics.

    The total accumulates a quantity, which is not always the quantity that was reported: a metric
    reported in watts is power, and adding power readings together totals nothing. Those are
    integrated over the interval they were measured on and totalled as watt-hours instead, so
    total_unit is what the total is in, and it is not always the unit of the metric.

    One report covers every series sharing a metric name, and a generator reporting per container
    gives them one name and different tags. Each series is integrated over the time since that same
    series was last reported, so a name carrying several of them totals all of them rather than
    only the one that happened to be reported first.
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

    def _record_the_interval_of(self, series: str, measured_at: float) -> None:
        """
        Add the interval this series just spanned to the average of the intervals seen.

        Measured on the series rather than on the name it shares, so that a name carrying several
        of them averages how often each reports and not how close together two of them landed.

        :param series: the series being reported
        :param measured_at: the time of the reading being recorded
        """
        measured_before = self._measured_at_by_series.get(series)
        if measured_before is None:
            return
        interval = measured_at - measured_before
        self.average_interval_in_seconds = (
            interval if not self.average_interval_in_seconds else (self.average_interval_in_seconds + interval) / 2
        )

    def _forget_the_series_that_stopped_reporting(self, measured_at: float) -> None:
        """
        Drop the series that have not reported for long enough to be gone.

        The key of a series carries the tags that identify it, and a container that restarts comes
        back under a new name, so keeping every key ever seen grows without a ceiling. A series
        that comes back after being forgotten opens a new window rather than measuring the whole
        absence, which is what it should do anyway.

        A name carrying several series reports them one after the other, so a horizon shorter
        than the interval they report on would let the first of them forget the ones still
        waiting their turn, and every window those spanned would be lost rather than totalled.
        The horizon is held above the interval that was measured for that reason.

        :param measured_at: the time of the reading being recorded
        """
        forgotten_after = max(
            _SERIES_ARE_FORGOTTEN_AFTER_SECONDS,
            _SERIES_ARE_FORGOTTEN_AFTER_INTERVALS * (self.average_interval_in_seconds or 0.0),
        )
        forgotten_before = measured_at - forgotten_after
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
        self._forget_the_series_that_stopped_reporting(measured_at=measured_at)

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
