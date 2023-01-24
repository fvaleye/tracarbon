from typing import Any, AsyncGenerator, Optional

from tracarbon.emissions import CarbonEmission, CarbonUsageUnit
from tracarbon.exporters import Metric, MetricGenerator, Tag
from tracarbon.hardwares import EnergyConsumption, EnergyUsageUnit, UsageType
from tracarbon.hardwares.containers import Kubernetes
from tracarbon.locations import Location


class EnergyConsumptionGenerator(MetricGenerator):
    """
    Energy consumption generator for energy consumption.
    """

    location: Location
    energy_consumption: EnergyConsumption

    def __init__(self, location: Location, **data: Any) -> None:
        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate a metric for energy consumption.

        :return: an async generator of the metrics
        """
        energy_usage = await self.energy_consumption.get_energy_usage()

        async def energy_usage_host() -> float:
            """
            Get the energy usage of the host.
            """
            return energy_usage.get_energy_usage_on_type(usage_type=UsageType.HOST)

        yield Metric(
            name="energy_consumption",
            value=energy_usage_host,
            tags=[
                Tag(key="platform", value=self.platform),
                Tag(key="location", value=self.location.name),
                Tag(key="units", value=energy_usage.unit.value),
            ],
        )


class EnergyConsumptionKubernetesGenerator(MetricGenerator):
    """
    Energy consumption generator for energy consumption of the containers.
    """

    location: Location
    energy_consumption: EnergyConsumption
    kubernetes: Kubernetes

    def __init__(self, **data: Any) -> None:
        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()
        if "kubernetes" not in data:
            data["kubernetes"] = Kubernetes()
        super().__init__(metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate metrics for the energy consumption with Kubernetes.

        :return: an async generator of the metrics
        """
        energy_usage = await self.energy_consumption.get_energy_usage()
        energy_usage.convert_unit(unit=EnergyUsageUnit.MILLIWATT)
        for pod in self.kubernetes.get_pods_usage():
            for container in pod.containers:

                async def get_container_energy_consumption() -> Optional[float]:
                    cpu_energy_usage = (
                        container.memory_usage * energy_usage.memory_energy_usage
                    )
                    memory_energy_usage = (
                        container.cpu_usage * energy_usage.cpu_energy_usage
                    )
                    return cpu_energy_usage + memory_energy_usage

                yield Metric(
                    name="energy_consumption_kubernetes",
                    value=get_container_energy_consumption,
                    tags=[
                        Tag(key="pod_name", value=pod.name),
                        Tag(key="pod_namespace", value=pod.namespace),
                        Tag(key="container_name", value=container.name),
                        Tag(key="platform", value=self.platform),
                        Tag(key="containers", value="kubernetes"),
                        Tag(key="location", value=self.location.name),
                        Tag(key="units", value=energy_usage.unit.value),
                    ],
                )


class CarbonEmissionGenerator(MetricGenerator):
    """
    Carbon emission generator to generate carbon emissions.
    """

    location: Location
    carbon_emission: CarbonEmission
    co2signal_api_key: Optional[str] = None

    def __init__(self, location: Location, **data: Any) -> None:
        if "carbon_emission" not in data:
            data["carbon_emission"] = CarbonEmission(
                co2signal_api_key=data["co2signal_api_key"]
                if "co2signal_api_key" in data
                else location.co2signal_api_key,
                location=location,
            )
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate metrics for the carbon emission.

        :return: an async generator of the metrics
        """
        carbon_usage = await self.carbon_emission.get_co2_usage()

        async def get_host_carbon_emission() -> float:
            """
            Return the host carbon usage.
            """
            return carbon_usage.host_carbon_usage

        yield Metric(
            name="carbon_emission",
            value=get_host_carbon_emission,
            tags=[
                Tag(key="platform", value=self.platform),
                Tag(key="location", value=self.location.name),
                Tag(key="source", value=self.location.co2g_kwh_source.value),
                Tag(key="units", value=carbon_usage.unit.value),
            ],
        )


class CarbonEmissionKubernetesGenerator(MetricGenerator):
    """
    Carbon emission generator to generate carbon emissions of the containers.
    """

    location: Location
    carbon_emission: CarbonEmission
    kubernetes: Kubernetes
    co2signal_api_key: Optional[str] = None

    def __init__(self, location: Location, **data: Any) -> None:
        if "carbon_emission" not in data:
            data["carbon_emission"] = CarbonEmission(
                co2signal_api_key=data["co2signal_api_key"]
                if "co2signal_api_key" in data
                else location.co2signal_api_key,
                location=location,
            )
        if "kubernetes" not in data:
            data["kubernetes"] = Kubernetes()
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate metrics for the carbon emission with Kubernetes.

        :return: an async generator of the metrics
        """
        carbon_usage = await self.carbon_emission.get_co2_usage()
        carbon_usage.convert_unit(unit=CarbonUsageUnit.CO2_MG_KWH)

        for pod in self.kubernetes.get_pods_usage():
            for container in pod.containers:

                async def get_container_carbon_emission() -> Optional[float]:
                    memory_co2 = (
                        container.memory_usage * carbon_usage.memory_carbon_usage
                    )
                    cpu_co2 = container.cpu_usage * carbon_usage.cpu_carbon_usage
                    return cpu_co2 + memory_co2

                yield Metric(
                    name="carbon_emission_kubernetes",
                    value=get_container_carbon_emission,
                    tags=[
                        Tag(key="pod_name", value=pod.name),
                        Tag(key="pod_namespace", value=pod.namespace),
                        Tag(key="container_name", value=container.name),
                        Tag(key="platform", value=self.platform),
                        Tag(key="containers", value="kubernetes"),
                        Tag(key="location", value=self.location.name),
                        Tag(key="source", value=self.location.co2g_kwh_source.value),
                        Tag(key="units", value=carbon_usage.unit.value),
                    ],
                )
