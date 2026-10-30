from typing import Any
from typing import AsyncGenerator

from pydantic import Field

from tracarbon._sampling import sample_energy
from tracarbon.emissions import CarbonEmission
from tracarbon.emissions import CarbonUsageUnit
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import Tag
from tracarbon.general_metrics import _carbon_emission
from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares import EnergyUsageUnit
from tracarbon.hardwares import UsageType
from tracarbon.hardwares.containers import Kubernetes
from tracarbon.locations import Location


class EnergyConsumptionKubernetesGenerator(MetricGenerator):
    """
    Energy consumption generator for energy consumption of the containers.
    """

    __module__ = "tracarbon.general_metrics"

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
        cpu_joules = energy_usage.interval_joules.get(UsageType.CPU)
        memory_joules = energy_usage.interval_joules.get(UsageType.MEMORY)
        for pod in self.kubernetes.get_pods_usage():
            for container in pod.containers:
                container_cpu_joules = cpu_joules * container.cpu_usage if cpu_joules is not None else None
                container_memory_joules = memory_joules * container.memory_usage if memory_joules is not None else None

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

    __module__ = "tracarbon.general_metrics"

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
