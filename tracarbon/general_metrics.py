from typing import Any, Optional

from tracarbon.emissions import CarbonEmission
from tracarbon.exporters import Metric, MetricGenerator, Tag
from tracarbon.hardwares import EnergyConsumption, HardwareInfo
from tracarbon.locations import Location


class EnergyConsumptionGenerator(MetricGenerator):
    """
    Energy consumption generator for energy consumption in watts.
    """

    location: Location

    def __init__(self, location: Location, **data: Any) -> None:
        metrics = [
            Metric(
                name="energy_consumption",
                value=EnergyConsumption.from_platform().run,
                tags=[
                    Tag(key="platform", value=HardwareInfo.get_platform()),
                    Tag(key="location", value=location.name),
                    Tag(key="units", value="watts"),
                ],
            )
        ]
        super().__init__(location=location, metrics=metrics, **data)


class CarbonEmissionGenerator(MetricGenerator):
    """
    Carbon emission generator for carbon emission in co2g/kwh.
    """

    location: Location
    co2signal_api_key: Optional[str] = None

    def __init__(self, location: Location, **data: Any) -> None:
        metrics = [
            Metric(
                name="carbon_emission",
                value=CarbonEmission(
                    co2signal_api_key=data["co2signal_api_key"]
                    if "co2signal_api_key" in data
                    else location.co2signal_api_key,
                    location=location,
                ).run,
                tags=[
                    Tag(key="platform", value=HardwareInfo.get_platform()),
                    Tag(key="location", value=location.name),
                    Tag(key="source", value=location.co2g_kwh_source.value),
                    Tag(key="units", value="co2g/kwh"),
                ],
            )
        ]
        super().__init__(location=location, metrics=metrics, **data)


class HardwareMemoryUsageGenerator(MetricGenerator):
    """
    Hardware memory usage generator for the memory % used of the total memory.
    """

    location: Location

    def __init__(self, location: Location, **data: Any) -> None:
        metrics = [
            Metric(
                name="hardware_memory_used",
                value=HardwareInfo.get_memory_usage,
                tags=[
                    Tag(key="platform", value=HardwareInfo.get_platform()),
                    Tag(key="location", value=location.name),
                    Tag(key="units", value="%"),
                ],
            )
        ]
        super().__init__(location=location, metrics=metrics, **data)


class HardwareCPUUsageGenerator(MetricGenerator):
    """
    Hardware CPU usage generator for the CPU % used of the total CPU.
    """

    location: Location

    def __init__(self, location: Location, **data: Any) -> None:
        metrics = [
            Metric(
                name="hardware_cpu_used",
                value=HardwareInfo.get_cpu_usage,
                tags=[
                    Tag(key="platform", value=HardwareInfo.get_platform()),
                    Tag(key="location", value=location.name),
                    Tag(key="units", value="%"),
                ],
            )
        ]
        super().__init__(location=location, metrics=metrics, **data)
