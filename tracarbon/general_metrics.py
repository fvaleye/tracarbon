from typing import Any
from typing import AsyncGenerator
from typing import Optional

from tracarbon.conf import KUBERNETES_INSTALLED
from tracarbon.emissions import CarbonEmission
from tracarbon.emissions import CarbonUsageUnit
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import Tag
from tracarbon.hardwares import EnergyConsumption
from tracarbon.hardwares import EnergyUsageUnit
from tracarbon.hardwares import UsageType
from tracarbon.locations import Country
from tracarbon.locations import Location


class EnergyConsumptionGenerator(MetricGenerator):
    """
    Energy consumption generator for energy consumption.
    """

    energy_consumption: EnergyConsumption

    def __init__(self, location: Optional[Location] = None, **data: Any) -> None:
        if "energy_consumption" not in data:
            data["energy_consumption"] = EnergyConsumption.from_platform()
        if not location:
            location = Country.get_location()
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate a metric for energy consumption.

        :return: an async generator of the metrics
        """
        energy_usage = await self.energy_consumption.get_energy_usage()

        for usage_type in UsageType:

            async def energy_consumption_by_usage_type() -> float:
                """
                Get the energy usage.
                """
                return energy_usage.get_energy_usage_on_type(usage_type=usage_type)

            yield Metric(
                name=f"energy_consumption_{usage_type.value}",
                value=energy_consumption_by_usage_type,
                tags=[
                    Tag(key="platform", value=self.platform),
                    Tag(key="location", value=self.location.name),
                    Tag(key="units", value=energy_usage.unit.value),
                ],
            )


class CarbonEmissionGenerator(MetricGenerator):
    """
    Carbon emission generator to generate carbon emissions.
    """

    carbon_emission: CarbonEmission
    co2signal_api_key: Optional[str] = None

    def __init__(self, location: Optional[Location] = None, **data: Any) -> None:
        if not location:
            location = Country.get_location()
        if "carbon_emission" not in data:
            data["carbon_emission"] = CarbonEmission(
                co2signal_api_key=(
                    data["co2signal_api_key"] if "co2signal_api_key" in data else location.co2signal_api_key
                ),
                co2signal_url=(data["co2signal_url"] if "co2signal_url" in data else location.co2signal_url),
                location=location,
            )
        super().__init__(location=location, metrics=[], **data)

    async def generate(self) -> AsyncGenerator[Metric, None]:
        """
        Generate metrics for the carbon emission.

        :return: an async generator of the metrics
        """
        carbon_usage = await self.carbon_emission.get_co2_usage()

        for usage_type in UsageType:

            async def get_carbon_emission_by_usage_type() -> float:
                """
                Get the carbon usage.
                """
                return carbon_usage.get_carbon_usage_on_type(usage_type=usage_type)

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

        async def generate(self) -> AsyncGenerator[Metric, None]:
            """
            Generate metrics for the energy consumption with Kubernetes.

            :return: an async generator of the metrics
            """
            energy_usage = await self.energy_consumption.get_energy_usage()
            energy_usage.convert_unit(unit=EnergyUsageUnit.MILLIWATT)
            for pod in self.kubernetes.get_pods_usage():
                for container in pod.containers:

                    async def get_pod_memory_energy_consumption() -> Optional[float]:
                        """
                        Get the memory energy consumption of the pod.
                        """
                        return container.memory_usage * energy_usage.memory_energy_usage

                    async def get_pod_cpu_energy_consumption() -> Optional[float]:
                        """
                        Get the CPU energy consumption of the pod.
                        """
                        return container.cpu_usage * energy_usage.cpu_energy_usage

                    async def get_pod_total_energy_consumption() -> Optional[float]:
                        """
                        Get the total energy consumption of the pod.
                        """
                        total = await get_pod_memory_energy_consumption() + await get_pod_cpu_energy_consumption()
                        return total

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
                    )
                    yield Metric(
                        name="energy_consumption_kubernetes_cpu",
                        value=get_pod_cpu_energy_consumption,
                        tags=tags,
                    )
                    yield Metric(
                        name="energy_consumption_kubernetes_memory",
                        value=get_pod_memory_energy_consumption,
                        tags=tags,
                    )

    class CarbonEmissionKubernetesGenerator(MetricGenerator):
        """
        Carbon emission generator to generate carbon emissions of the containers.
        """

        carbon_emission: CarbonEmission
        kubernetes: Kubernetes
        co2signal_api_key: Optional[str] = None

        def __init__(self, location: Location, **data: Any) -> None:
            if "carbon_emission" not in data:
                data["carbon_emission"] = CarbonEmission(
                    co2signal_api_key=(
                        data["co2signal_api_key"] if "co2signal_api_key" in data else location.co2signal_api_key
                    ),
                    co2signal_url=(data["co2signal_url"] if "co2signal_url" in data else location.co2signal_url),
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
            carbon_usage.convert_unit(unit=CarbonUsageUnit.CO2_MG)

            for pod in self.kubernetes.get_pods_usage():
                for container in pod.containers:

                    async def get_cpu_pod_carbon_emission() -> Optional[float]:
                        """
                        Get the CPU carbon emission of the pod.
                        """
                        return container.cpu_usage * carbon_usage.cpu_carbon_usage

                    async def get_memory_pod_carbon_emission() -> Optional[float]:
                        """
                        Get the memory carbon emission of the pod.
                        """
                        return container.memory_usage * carbon_usage.memory_carbon_usage

                    async def get_total_pod_carbon_emission() -> Optional[float]:
                        """
                        Get the total carbon emission of the pod.
                        """
                        total = await get_cpu_pod_carbon_emission() + await get_memory_pod_carbon_emission()
                        return total

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
