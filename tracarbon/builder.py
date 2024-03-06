import datetime
from typing import Dict
from typing import Optional

from pydantic import BaseModel

from tracarbon.conf import TracarbonConfiguration
from tracarbon.exporters import Exporter
from tracarbon.exporters import MetricReport
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.locations import Country
from tracarbon.locations import Location


class TracarbonReport(BaseModel):
    """
    Tracarbon report to store running statistics.
    """

    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    metric_report: Dict[str, MetricReport] = dict()

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class Tracarbon:
    """
    Tracarbon instance.
    """

    configuration: TracarbonConfiguration
    exporter: Exporter
    location: Location
    report: TracarbonReport = TracarbonReport()

    def __init__(
        self,
        configuration: TracarbonConfiguration,
        exporter: Optional[Exporter],
        location: Optional[Location],
    ) -> None:
        self.configuration = configuration
        self.exporter = exporter
        self.location = location

    def __enter__(self) -> None:
        self.start()

    def __exit__(self, type, value, traceback) -> None:  # type: ignore
        self.stop()

    def start(self) -> None:
        """
        Start Tracarbon.
        """
        self.report.start_time = datetime.datetime.now()
        self.exporter.start(interval_in_seconds=self.configuration.interval_in_seconds)

    def stop(self) -> None:
        """
        Stop Tracarbon.
        """
        self.report.metric_report = self.exporter.metric_report
        self.report.end_time = datetime.datetime.now()
        self.exporter.stop()


class TracarbonBuilder(BaseModel):
    """
    Tracarbon builder for building Tracarbon.
    """

    exporter: Optional[Exporter] = None
    location: Optional[Location] = None
    configuration: TracarbonConfiguration = TracarbonConfiguration()

    def with_location(self, location: Location) -> "TracarbonBuilder":
        """
        Add a location to the builder.
        :param location: the location
        :return:
        """
        self.location = location
        return self

    def with_exporter(self, exporter: Exporter) -> "TracarbonBuilder":
        """
        Add an exporter to the builder.
        :param exporter: the exporter
        :return:
        """
        self.exporter = exporter
        return self

    def build(self) -> Tracarbon:
        """
        Build Tracarbon with its configuration.
        """
        if not self.location:
            self.location = Country.get_location(
                co2signal_api_key=self.configuration.co2signal_api_key,
                co2signal_url=self.configuration.co2signal_url,
            )
        if not self.exporter:
            self.exporter = StdoutExporter(metric_generators=[CarbonEmissionGenerator(location=self.location)])

        return Tracarbon(
            configuration=self.configuration,
            exporter=self.exporter,
            location=self.location,
        )
