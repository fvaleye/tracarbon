import pytest
from kubernetes import config

from tracarbon import (
    CarbonEmission,
    CarbonUsage,
    EnergyConsumption,
    EnergyUsage,
    HardwareInfo,
    Kubernetes,
    MacEnergyConsumption,
)
from tracarbon.exporters import Tag
from tracarbon.general_metrics import (
    CarbonEmissionGenerator,
    CarbonEmissionKubernetesGenerator,
    EnergyConsumptionGenerator,
    EnergyConsumptionKubernetesGenerator,
)
from tracarbon.hardwares import Container, Pod
from tracarbon.locations.country import Country


@pytest.mark.asyncio
async def test_carbon_emission_metric(mocker):
    location_name = "fr"
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(CarbonEmission, "get_energy_usage", return_value=energy_usage)
    location = Country(name=location_name, co2g_kwh=51.1)
    carbon_emission_generator = CarbonEmissionGenerator(location=location)
    carbon_emission_metric = await carbon_emission_generator.generate().__anext__()

    assert carbon_emission_metric.name == "carbon_emission"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(
        key="source", value=location.co2g_kwh_source.value
    )
    assert carbon_emission_metric.tags[3] == Tag(key="units", value="co2g/kwh")


@pytest.mark.asyncio
async def test_energy_consumption_metric(mocker):
    location_name = "fr"
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(
        EnergyConsumption, "from_platform", return_value=MacEnergyConsumption()
    )
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=energy_usage
    )
    location = Country(name=location_name, co2g_kwh=51.1)
    energy_consumption_generator = EnergyConsumptionGenerator(location=location)
    energy_consumption_metric = (
        await energy_consumption_generator.generate().__anext__()
    )

    assert energy_consumption_metric.name == "energy_consumption"
    assert energy_consumption_metric.tags[1] == Tag(key="location", value=location_name)
    assert energy_consumption_metric.tags[2] == Tag(key="units", value="watts")


@pytest.mark.asyncio
async def test_energy_consumption_kubernetes_generator(mocker):
    location_name = "fr"
    memory_total = 101200121856
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(
        EnergyConsumption, "from_platform", return_value=MacEnergyConsumption()
    )
    mocker.patch.object(config, "load_kube_config", return_value=None)
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=memory_total)
    cores_number = 2
    mocker.patch.object(HardwareInfo, "get_number_of_cores", return_value=cores_number)
    mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=energy_usage
    )
    container_name = "grafana"
    pod_name = "grafana-5745b58656-8q4q8"
    namespace = "default"
    pods_usage = [
        Pod(
            name=pod_name,
            namespace=namespace,
            containers=[
                Container(
                    name=container_name,
                    cpu_usage="825800n",
                    memory_usage="46472Ki",
                )
            ],
        ),
    ]
    milliwatts_expected = 6.7916
    mocker.patch.object(Kubernetes, "get_pods_usage", return_value=pods_usage)

    location = Country(name=location_name, co2g_kwh=51.1)
    energy_consumption_kubernertes_generator = EnergyConsumptionKubernetesGenerator(
        location=location, platform="Darwin"
    )

    async_generator = energy_consumption_kubernertes_generator.generate()
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == milliwatts_expected
    assert "energy_consumption_kubernetes" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "units:milliwatts",
    ] == metric.format_tags()


@pytest.mark.asyncio
async def test_carbon_emission_kubernetes_generator(mocker):
    location_name = "fr"
    memory_total = 1000000000
    carbon_usage = CarbonUsage(cpu_carbon_usage=0.2, memory_carbon_usage=0.1)
    mocker.patch.object(
        EnergyConsumption, "from_platform", return_value=MacEnergyConsumption()
    )
    mocker.patch.object(config, "load_kube_config", return_value=None)
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=memory_total)
    cores_number = 2
    mocker.patch.object(HardwareInfo, "get_number_of_cores", return_value=cores_number)
    mocker.patch.object(CarbonEmission, "get_co2_usage", return_value=carbon_usage)
    container_name = "grafana"
    pod_name = "grafana-5745b58656-8q4q8"
    namespace = "default"
    pods_usage = [
        Pod(
            name=pod_name,
            namespace=namespace,
            containers=[
                Container(
                    name=container_name,
                    cpu_usage="2000m",
                    memory_usage="1Gi",
                )
            ],
        ),
    ]
    carbon_usage_expected = 300.00
    mocker.patch.object(Kubernetes, "get_pods_usage", return_value=pods_usage)

    location = Country(name=location_name, co2g_kwh=55)
    carbon_emission_kubernertes_generator = CarbonEmissionKubernetesGenerator(
        location=location, platform="Darwin"
    )

    async_generator = carbon_emission_kubernertes_generator.generate()
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == carbon_usage_expected
    assert "carbon_emission_kubernetes" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "source:file",
        "units:co2mg/kwh",
    ] == metric.format_tags()
