from typing import Any, Awaitable, Callable, List, Optional

from tracarbon.emissions import CarbonEmission
from tracarbon.exporters import Metric, Tag
from tracarbon.hardwares import EnergyConsumption, HardwareInfo
from tracarbon.locations import Location


class EnergyConsumptionMetric(Metric):
    """
    Energy consumption metric in watts.
    """

    location: Location
    platform: str = HardwareInfo.get_platform()
    name: str = "energy_consumption"
    value: Optional[Callable[[], Awaitable[float]]] = None  # type: ignore
    tags: List[Tag] = list()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if "tags" not in data:
            self.tags = [
                Tag(key="platform", value=self.platform),
                Tag(key="location", value=self.location.name),
                Tag(key="units", value="watts"),
            ]
        if "value" not in data:
            self.value = EnergyConsumption.from_platform().run


class CarbonEmissionMetric(Metric):
    """
    Carbon emission metric in co2g/kwh.
    """

    location: Location
    platform: str = HardwareInfo.get_platform()
    name: str = "carbon_emission"
    co2signal_api_key: Optional[str] = None
    value: Optional[Callable[[], Awaitable[float]]] = None  # type: ignore
    tags: List[Tag] = list()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if "tags" not in data:
            self.tags = [
                Tag(key="platform", value=self.platform),
                Tag(key="location", value=self.location.name),
                Tag(key="source", value=self.location.co2g_kwh_source.value),
                Tag(key="units", value="co2g/kwh"),
            ]
        if "value" not in data:
            self.value = CarbonEmission(
                co2signal_api_key=self.co2signal_api_key
                if self.co2signal_api_key
                else self.location.co2signal_api_key,
                location=self.location,
            ).run


class HardwareMemoryUsageMetric(Metric):
    """
    Hardware memory usage metric in % used for the total memory.
    """

    location: Location
    platform: str = HardwareInfo.get_platform()
    name: str = "hardware_memory_used"
    value: Callable[[], Awaitable[float]] = HardwareInfo.get_memory_usage
    tags: List[Tag] = list()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if "tags" not in data:
            self.tags = [
                Tag(key="platform", value=self.platform),
                Tag(key="location", value=self.location.name),
                Tag(key="units", value="%"),
            ]


class HardwareCPUUsageMetric(Metric):
    """
    Hardware CPU usage metric in % used for the total CPU.
    """

    location: Location
    platform: str = HardwareInfo.get_platform()
    name: str = "hardware_cpu_used"
    value: Callable[[], Awaitable[float]] = HardwareInfo.get_cpu_usage
    tags: List[Tag] = list()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if "tags" not in data:
            self.tags = [
                Tag(key="platform", value=self.platform),
                Tag(key="location", value=self.location.name),
                Tag(key="units", value="%"),
            ]
