from typing import Any
from typing import AsyncGenerator
from typing import Dict
from typing import Iterable

from pydantic import Field

from tracarbon import conf as _conf
from tracarbon._sampling import sample_energy
from tracarbon._sampling import sample_processes
from tracarbon.emissions import CarbonEmission
from tracarbon.emissions import CarbonUsageUnit as CarbonUsageUnit
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import Tag
from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares import EnergyUsageUnit as EnergyUsageUnit
from tracarbon.hardwares import UsageType
from tracarbon.hardwares.processes import Processes
from tracarbon.locations import Country
from tracarbon.locations import Location


def _carbon_emission(location: Location, data: Dict[str, Any]) -> CarbonEmission:
    """Create a carbon sensor, preferring explicit API settings over location defaults."""
    return CarbonEmission(
        co2signal_api_key=data.get("co2signal_api_key", location.co2signal_api_key),
        co2signal_url=data.get("co2signal_url", location.co2signal_url),
        location=location,
    )


class EnergyConsumptionGenerator(MetricGenerator):
    """
    Energy consumption generator for energy consumption.
    """

    energy_consumption: EnergyConsumption

    def __init__(self, location: Location | None = None, **data: Any) -> None:
        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()
        if not location:
            location = Country.get_location()
        super().__init__(location=location, metrics=[], **data)

    def reset(self) -> None:
        self.energy_consumption.reset()

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate a metric for energy consumption.

        :return: an async generator of the metrics
        """
        energy_usage = await sample_energy(self.energy_consumption)

        for usage_type in UsageType:

            async def energy_consumption_by_usage_type(ut=usage_type) -> float | None:
                """
                Get the energy usage.
                """
                return energy_usage.get_energy_usage_on_type(usage_type=ut)

            if self.location is None:
                raise ValueError("Location must be set")
            yield Metric(
                name=f"energy_consumption_{usage_type.value}",
                value=energy_consumption_by_usage_type,
                tags=[
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="units", value=energy_usage.unit.value),
                ],
                interval_joules=energy_usage.interval_joules.get(usage_type),
            )


class CarbonEmissionGenerator(MetricGenerator):
    """
    Carbon emission generator to generate carbon emissions.
    """

    carbon_emission: CarbonEmission
    co2signal_api_key: str | None = Field(default=None, repr=False)

    def reset(self) -> None:
        self.carbon_emission.reset()

    def __init__(self, location: Location | None = None, **data: Any) -> None:
        if not location:
            location = Country.get_location()
        if "carbon_emission" not in data:
            data["carbon_emission"] = _carbon_emission(location=location, data=data)
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate metrics for the carbon emission.

        :return: an async generator of the metrics
        """
        carbon_usage = await self.carbon_emission.get_co2_usage()

        for usage_type in UsageType:

            async def get_carbon_emission_by_usage_type(ut=usage_type) -> float | None:
                """
                Get the carbon usage.
                """
                return carbon_usage.get_carbon_usage_on_type(usage_type=ut)

            if self.location is None:
                raise ValueError("Location must be set")
            yield Metric(
                name=f"carbon_emission_{usage_type.value}",
                value=get_carbon_emission_by_usage_type,
                tags=[
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="source", value=self.location.co2g_kwh_source.value),
                    Tag(key="units", value=carbon_usage.unit.value),
                ],
            )


class EnergyConsumptionProcessGenerator(MetricGenerator):
    """Attribute host CPU power to process trees."""

    energy_consumption: EnergyConsumption
    processes: Processes

    def reset(self) -> None:
        self.energy_consumption.reset()
        self.processes.reset()

    def __init__(self, pids: Iterable[int] = (), **data: Any) -> None:
        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()
        if "processes" not in data:
            data["processes"] = Processes(pids=list(pids))
        super().__init__(metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """Yield process CPU power with PID, name, location and unit labels."""
        energy_usage = await sample_energy(self.energy_consumption)
        cpu_joules = energy_usage.interval_joules.get(UsageType.CPU)
        for process in sample_processes(self.processes):

            async def get_process_cpu_energy_consumption(p=process) -> float | None:
                if energy_usage.cpu_energy_usage is None:
                    return None
                return p.cpu_usage * energy_usage.cpu_energy_usage

            if self.location is None:
                raise ValueError("Location must be set")
            yield Metric(
                name="energy_consumption_process_cpu",
                value=get_process_cpu_energy_consumption,
                tags=[
                    Tag(key="pid", value=str(process.pid)),
                    Tag(key="process_name", value=process.name),
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="units", value=energy_usage.unit.value),
                ],
                interval_joules=cpu_joules * process.cpu_usage if cpu_joules is not None else None,
            )


class CarbonEmissionProcessGenerator(MetricGenerator):
    """Attribute host CPU carbon emissions to process trees."""

    carbon_emission: CarbonEmission
    processes: Processes
    co2signal_api_key: str | None = Field(default=None, repr=False)

    def reset(self) -> None:
        self.carbon_emission.reset()
        self.processes.reset()

    def __init__(self, location: Location, pids: Iterable[int] = (), **data: Any) -> None:
        if "carbon_emission" not in data:
            data["carbon_emission"] = _carbon_emission(location=location, data=data)
        if "processes" not in data:
            data["processes"] = Processes(pids=list(pids))
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """Yield process CPU carbon with PID, name, location, source and unit labels."""
        carbon_usage = await self.carbon_emission.get_co2_usage()
        for process in sample_processes(self.processes):

            async def get_process_cpu_carbon_emission(p=process) -> float | None:
                if carbon_usage.cpu_carbon_usage is None:
                    return None
                return p.cpu_usage * carbon_usage.cpu_carbon_usage

            if self.location is None:
                raise ValueError("Location must be set")
            yield Metric(
                name="carbon_emission_process_cpu",
                value=get_process_cpu_carbon_emission,
                tags=[
                    Tag(key="pid", value=str(process.pid)),
                    Tag(key="process_name", value=process.name),
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="source", value=self.location.co2g_kwh_source.value),
                    Tag(key="units", value=carbon_usage.unit.value),
                ],
            )


_KUBERNETES_EXPORTS = ("CarbonEmissionKubernetesGenerator", "EnergyConsumptionKubernetesGenerator", "Kubernetes")


def __getattr__(name: str) -> Any:
    if name == "KUBERNETES_INSTALLED":
        return _conf.KUBERNETES_INSTALLED
    if name == "__all__":
        exports = {key for key in globals() if not key.startswith("_")} | {"KUBERNETES_INSTALLED"}
        if _conf.KUBERNETES_INSTALLED:
            exports.update(_KUBERNETES_EXPORTS)
        return sorted(exports)
    if name in _KUBERNETES_EXPORTS and _conf.KUBERNETES_INSTALLED:
        from tracarbon import _kubernetes_metrics

        value = getattr(_kubernetes_metrics, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__getattr__("__all__")))


def _process_generators(
    location: Location, pids: Iterable[int], energy_consumption: EnergyConsumption | None = None
) -> list[MetricGenerator]:
    data = {"energy_consumption": energy_consumption} if energy_consumption is not None else {}
    energy = EnergyConsumptionProcessGenerator(location=location, pids=pids, **data)
    carbon = CarbonEmissionProcessGenerator(
        location=location,
        processes=energy.processes,
        carbon_emission=CarbonEmission(location=location, energy_consumption=energy.energy_consumption),
    )
    return [energy, carbon]
