from typing import Any
from typing import AsyncGenerator
from typing import Dict
from typing import Iterable

from pydantic import Field

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
        energy_usage = await self.energy_consumption.get_energy_usage()

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
        energy_usage = await self.energy_consumption.get_energy_usage()
        cpu_joules = energy_usage.interval_joules.get(UsageType.CPU)
        for process in self.processes.get_processes_usage():

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
        for process in self.processes.get_processes_usage():

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
            energy_usage = await self.energy_consumption.get_energy_usage()
            energy_usage.convert_unit(unit=EnergyUsageUnit.MILLIWATT)
            cpu_joules = energy_usage.interval_joules.get(UsageType.CPU)
            memory_joules = energy_usage.interval_joules.get(UsageType.MEMORY)
            for pod in self.kubernetes.get_pods_usage():
                for container in pod.containers:
                    container_cpu_joules = cpu_joules * container.cpu_usage if cpu_joules is not None else None
                    container_memory_joules = (
                        memory_joules * container.memory_usage if memory_joules is not None else None
                    )

                    async def get_pod_memory_energy_consumption(c=container) -> float | None:
                        """
                        Get the memory energy consumption of the pod.
                        """
                        if energy_usage.memory_energy_usage is None:
                            return None
                        return c.memory_usage * energy_usage.memory_energy_usage

                    async def get_pod_cpu_energy_consumption(c=container) -> float | None:
                        """
                        Get the CPU energy consumption of the pod.
                        """
                        if energy_usage.cpu_energy_usage is None:
                            return None
                        return c.cpu_usage * energy_usage.cpu_energy_usage

                    async def get_pod_total_energy_consumption(
                        _mem=get_pod_memory_energy_consumption, _cpu=get_pod_cpu_energy_consumption
                    ) -> float | None:
                        """
                        Get the total energy consumption of the pod.
                        """
                        memory = await _mem()
                        cpu = await _cpu()
                        if memory is None or cpu is None:
                            return None
                        return memory + cpu

                    if self.location is None:
                        raise ValueError("Location must be set")
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
                        value=get_pod_total_energy_consumption,
                        tags=tags,
                        interval_joules=container_cpu_joules + container_memory_joules
                        if container_cpu_joules is not None and container_memory_joules is not None
                        else None,
                    )
                    yield Metric(
                        name="energy_consumption_kubernetes_cpu",
                        value=get_pod_cpu_energy_consumption,
                        tags=tags,
                        interval_joules=container_cpu_joules,
                    )
                    yield Metric(
                        name="energy_consumption_kubernetes_memory",
                        value=get_pod_memory_energy_consumption,
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

            for pod in self.kubernetes.get_pods_usage():
                for container in pod.containers:

                    async def get_cpu_pod_carbon_emission(c=container) -> float | None:
                        """
                        Get the CPU carbon emission of the pod.
                        """
                        if carbon_usage.cpu_carbon_usage is None:
                            return None
                        return c.cpu_usage * carbon_usage.cpu_carbon_usage

                    async def get_memory_pod_carbon_emission(c=container) -> float | None:
                        """
                        Get the memory carbon emission of the pod.
                        """
                        if carbon_usage.memory_carbon_usage is None:
                            return None
                        return c.memory_usage * carbon_usage.memory_carbon_usage

                    async def get_total_pod_carbon_emission(
                        _cpu=get_cpu_pod_carbon_emission, _mem=get_memory_pod_carbon_emission
                    ) -> float | None:
                        """
                        Get the total carbon emission of the pod.
                        """
                        cpu = await _cpu()
                        memory = await _mem()
                        if cpu is None or memory is None:
                            return None
                        return cpu + memory

                    if self.location is None:
                        raise ValueError("Location must be set")
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
                        value=get_total_pod_carbon_emission,
                        tags=tags,
                    )
                    yield Metric(
                        name="carbon_emission_kubernetes_cpu",
                        value=get_cpu_pod_carbon_emission,
                        tags=tags,
                    )
                    yield Metric(
                        name="carbon_emission_kubernetes_memory",
                        value=get_memory_pod_carbon_emission,
                        tags=tags,
                    )
