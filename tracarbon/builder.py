from typing import List, Optional

from pydantic import BaseModel

from tracarbon.conf import TracarbonConfiguration
from tracarbon.emissions import CarbonEmission
from tracarbon.exporters import Exporter, Metric, StdoutExporter, Tag
from tracarbon.hardwares import HardwareInfo
from tracarbon.locations import Country, Location


class Tracarbon:
    """
    Tracarbon instance.
    """

    configuration: TracarbonConfiguration
    exporter: Exporter
    location: Location

    def __init__(
        self,
        configuration: TracarbonConfiguration,
        exporter: Optional[Exporter],
        location: Optional[Location],
    ) -> None:
        self.configuration = configuration
        if location:
            self.location = location
        else:
            self.location = Country.get_location(
                co2signal_api_key=configuration.co2signal_api_key,
            )
        if exporter:
            self.exporter = exporter
        else:
            self.exporter = StdoutExporter(
                metrics=[
                    Metric(
                        name="co2_emission",
                        value=CarbonEmission(location=self.location).run,
                        tags=[
                            Tag(key="platform", value=HardwareInfo.get_platform()),
                            Tag(key="location", value=self.location.name),
                        ],
                    )
                ]
            )

    def __enter__(self) -> None:
        self.exporter.start(interval_in_seconds=self.configuration.interval_in_seconds)

    def __exit__(self, type, value, traceback) -> None:  # type: ignore
        self.exporter.stop()

    def start(self) -> None:
        """
        Start Tracarbon.
        """
        self.exporter.start(interval_in_seconds=self.configuration.interval_in_seconds)

    def stop(self) -> None:
        """
        Stop Tracarbon.
        """
        self.exporter.stop()


class TracarbonBuilder(BaseModel):
    """
    Tracarbon builder for building Tracarbon.
    """

    configuration: TracarbonConfiguration = TracarbonConfiguration()

    def build(
        self, exporter: Optional[Exporter] = None, location: Optional[Location] = None
    ) -> Tracarbon:
        """
        Build Tracarbon with its configuration.

        :param exporter: the exporter to use
        :param location: the location to use
        """

        return Tracarbon(
            configuration=self.configuration,
            exporter=exporter,
            location=location,
        )
