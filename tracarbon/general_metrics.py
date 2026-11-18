from typing import Any
from typing import AsyncGenerator
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import Iterable

from pydantic import Field

from tracarbon._sampling import sample_energy
from tracarbon._sampling import sample_processes
from tracarbon.conf import KUBERNETES_INSTALLED
from tracarbon.emissions import CarbonEmission
from tracarbon.emissions import CarbonUsageUnit
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import Tag
from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares import EnergyUsageUnit
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


def _share_of(share: float, total: float | None) -> float | None:
    return None if total is None else share * total


def _total(cpu: float | None, memory: float | None) -> float | None:
    return None if cpu is None or memory is None else cpu + memory


def _returning(value: float | None) -> Callable[[], Awaitable[float | None]]:
    async def read() -> float | None:
        return value

    return read


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
        if self.location is None:
            raise ValueError("Location must be set")
        for usage_type in UsageType:
            yield Metric(
                name=f"energy_consumption_{usage_type.value}",
                value=_returning(energy_usage.get_energy_usage_on_type(usage_type=usage_type)),
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
        if self.location is None:
            raise ValueError("Location must be set")
        for usage_type in UsageType:
            yield Metric(
                name=f"carbon_emission_{usage_type.value}",
                value=_returning(carbon_usage.get_carbon_usage_on_type(usage_type=usage_type)),
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
        if self.location is None:
            raise ValueError("Location must be set")
        cpu_joules = energy_usage.interval_joules.get(UsageType.CPU)
        for process in sample_processes(self.processes):
            yield Metric(
                name="energy_consumption_process_cpu",
                value=_returning(_share_of(process.cpu_usage, energy_usage.cpu_energy_usage)),
                tags=[
                    Tag(key="pid", value=str(process.pid)),
                    Tag(key="process_name", value=process.name),
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="units", value=energy_usage.unit.value),
                ],
                interval_joules=_share_of(process.cpu_usage, cpu_joules),
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
        if self.location is None:
            raise ValueError("Location must be set")
        for process in sample_processes(self.processes):
            yield Metric(
                name="carbon_emission_process_cpu",
                value=_returning(_share_of(process.cpu_usage, carbon_usage.cpu_carbon_usage)),
                tags=[
                    Tag(key="pid", value=str(process.pid)),
                    Tag(key="process_name", value=process.name),
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="source", value=self.location.co2g_kwh_source.value),
                    Tag(key="units", value=carbon_usage.unit.value),
                ],
            )


if KUBERNETES_INSTALLED:
    from tracarbon.hardwares.containers import Kubernetes

    class EnergyConsumptionKubernetesGenerator(MetricGenerator):
        """
        Energy consumption generator for energy consumption of the containers.
        """

        energy_consumption: EnergyConsumption
        kubernetes: Kubernetes

        def __init__(self, **data: Any) -> None:
            if "energy_consumption" not in data:
                data["energy_consumption"] = EnergyConsumption.from_platform()
            if "kubernetes" not in data:
                data["kubernetes"] = Kubernetes()
            super().__init__(metrics=[], **data)

        def reset(self) -> None:
            self.energy_consumption.reset()

        async def generate(self) -> AsyncGenerator[Metric, None]:
            """
            Generate metrics for the energy consumption with Kubernetes.

            :return: an async generator of the metrics
            """
            energy_usage = await sample_energy(self.energy_consumption)
            energy_usage.convert_unit(unit=EnergyUsageUnit.MILLIWATT)
            if self.location is None:
                raise ValueError("Location must be set")
            cpu_joules = energy_usage.interval_joules.get(UsageType.CPU)
            memory_joules = energy_usage.interval_joules.get(UsageType.MEMORY)
            for pod in self.kubernetes.get_pods_usage():
                for container in pod.containers:
                    container_cpu_energy_usage = _share_of(container.cpu_usage, energy_usage.cpu_energy_usage)
                    container_memory_energy_usage = _share_of(container.memory_usage, energy_usage.memory_energy_usage)
                    container_cpu_joules = _share_of(container.cpu_usage, cpu_joules)
                    container_memory_joules = _share_of(container.memory_usage, memory_joules)
                    tags = [
                        Tag(key="pod_name", value=pod.name),
                        Tag(key="pod_namespace", value=pod.namespace),
                        Tag(key="container_name", value=container.name),
                        Tag(key="platform", value=self.platform),
                        Tag(key="containers", value="kubernetes"),
                        Tag(key="location", value=self.location.name),
                        Tag(key="units", value=energy_usage.unit.value),
                    ]

                    yield Metric(
                        name="energy_consumption_kubernetes_total",
                        value=_returning(_total(container_cpu_energy_usage, container_memory_energy_usage)),
                        tags=tags,
                        interval_joules=_total(container_cpu_joules, container_memory_joules),
                    )
                    yield Metric(
                        name="energy_consumption_kubernetes_cpu",
                        value=_returning(container_cpu_energy_usage),
                        tags=tags,
                        interval_joules=container_cpu_joules,
                    )
                    yield Metric(
                        name="energy_consumption_kubernetes_memory",
                        value=_returning(container_memory_energy_usage),
                        tags=tags,
                        interval_joules=container_memory_joules,
                    )

    class CarbonEmissionKubernetesGenerator(MetricGenerator):
        """
        Carbon emission generator to generate carbon emissions of the containers.
        """

        carbon_emission: CarbonEmission
        kubernetes: Kubernetes
        co2signal_api_key: str | None = Field(default=None, repr=False)

        def reset(self) -> None:
            self.carbon_emission.reset()

        def __init__(self, location: Location, **data: Any) -> None:
            if "carbon_emission" not in data:
                data["carbon_emission"] = _carbon_emission(location=location, data=data)
            if "kubernetes" not in data:
                data["kubernetes"] = Kubernetes()
            super().__init__(location=location, metrics=[], **data)

        async def generate(self) -> AsyncGenerator[Metric, None]:
            """
            Generate metrics for the carbon emission with Kubernetes.

            :return: an async generator of the metrics
            """
            carbon_usage = await self.carbon_emission.get_co2_usage()
            carbon_usage.convert_unit(unit=CarbonUsageUnit.CO2_MG)
            if self.location is None:
                raise ValueError("Location must be set")
            for pod in self.kubernetes.get_pods_usage():
                for container in pod.containers:
                    container_cpu_carbon_usage = _share_of(container.cpu_usage, carbon_usage.cpu_carbon_usage)
                    container_memory_carbon_usage = _share_of(container.memory_usage, carbon_usage.memory_carbon_usage)
                    tags = [
                        Tag(key="pod_name", value=pod.name),
                        Tag(key="pod_namespace", value=pod.namespace),
                        Tag(key="container_name", value=container.name),
                        Tag(key="platform", value=self.platform),
                        Tag(key="containers", value="kubernetes"),
                        Tag(key="location", value=self.location.name),
                        Tag(key="source", value=self.location.co2g_kwh_source.value),
                        Tag(key="units", value=carbon_usage.unit.value),
                    ]
                    yield Metric(
                        name="carbon_emission_kubernetes_total",
                        value=_returning(_total(container_cpu_carbon_usage, container_memory_carbon_usage)),
                        tags=tags,
                    )
                    yield Metric(
                        name="carbon_emission_kubernetes_cpu",
                        value=_returning(container_cpu_carbon_usage),
                        tags=tags,
                    )
                    yield Metric(
                        name="carbon_emission_kubernetes_memory",
                        value=_returning(container_memory_carbon_usage),
                        tags=tags,
                    )


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
