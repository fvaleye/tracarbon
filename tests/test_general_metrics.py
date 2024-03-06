import pytest
from kubernetes import config

from tracarbon import CarbonEmission
from tracarbon import CarbonUsage
from tracarbon import EnergyConsumption
from tracarbon import EnergyUsage
from tracarbon import HardwareInfo
from tracarbon import Kubernetes
from tracarbon import MacEnergyConsumption
from tracarbon.exporters import Tag
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import CarbonEmissionKubernetesGenerator
from tracarbon.general_metrics import EnergyConsumptionGenerator
from tracarbon.general_metrics import EnergyConsumptionKubernetesGenerator
from tracarbon.hardwares import Container
from tracarbon.hardwares import Pod
from tracarbon.locations.country import Country


@pytest.mark.asyncio
async def test_carbon_emission_metric(mocker):
    location_name = "fr"
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(CarbonEmission, "get_energy_usage", return_value=energy_usage)
    location = Country(name=location_name, co2g_kwh=51.1)
    carbon_emission_generator = CarbonEmissionGenerator(location=location)
    generator = carbon_emission_generator.generate()
    carbon_emission_metric = await generator.__anext__()

    assert carbon_emission_metric.name == "carbon_emission_host"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="source", value=location.co2g_kwh_source.value)
    assert carbon_emission_metric.tags[3] == Tag(key="units", value="co2g")

    carbon_emission_metric = await generator.__anext__()
    assert carbon_emission_metric.name == "carbon_emission_cpu"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="source", value=location.co2g_kwh_source.value)
    assert carbon_emission_metric.tags[3] == Tag(key="units", value="co2g")

    carbon_emission_metric = await generator.__anext__()
    assert carbon_emission_metric.name == "carbon_emission_memory"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="source", value=location.co2g_kwh_source.value)
    assert carbon_emission_metric.tags[3] == Tag(key="units", value="co2g")

    carbon_emission_metric = await generator.__anext__()
    assert carbon_emission_metric.name == "carbon_emission_gpu"
    assert carbon_emission_metric.tags[1] == Tag(key="location", value=location_name)
    assert carbon_emission_metric.tags[2] == Tag(key="source", value=location.co2g_kwh_source.value)
    assert carbon_emission_metric.tags[3] == Tag(key="units", value="co2g")


@pytest.mark.asyncio
async def test_energy_consumption_metric(mocker):
    location_name = "fr"
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=MacEnergyConsumption())
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=energy_usage)
    location = Country(name=location_name, co2g_kwh=51.1)
    energy_consumption_generator = EnergyConsumptionGenerator(location=location)
    generator = energy_consumption_generator.generate()
    energy_consumption_metric = await generator.__anext__()

    assert energy_consumption_metric.name == "energy_consumption_host"
    assert energy_consumption_metric.tags[1] == Tag(key="location", value=location_name)
    assert energy_consumption_metric.tags[2] == Tag(key="units", value="watts")

    energy_consumption_metric = await generator.__anext__()
    assert energy_consumption_metric.name == "energy_consumption_cpu"
    assert energy_consumption_metric.tags[1] == Tag(key="location", value=location_name)
    assert energy_consumption_metric.tags[2] == Tag(key="units", value="watts")

    energy_consumption_metric = await generator.__anext__()
    assert energy_consumption_metric.name == "energy_consumption_memory"
    assert energy_consumption_metric.tags[1] == Tag(key="location", value=location_name)
    assert energy_consumption_metric.tags[2] == Tag(key="units", value="watts")

    energy_consumption_metric = await generator.__anext__()
    assert energy_consumption_metric.name == "energy_consumption_gpu"
    assert energy_consumption_metric.tags[1] == Tag(key="location", value=location_name)
    assert energy_consumption_metric.tags[2] == Tag(key="units", value="watts")


@pytest.mark.asyncio
async def test_energy_consumption_kubernetes_generator(mocker):
    location_name = "fr"
    memory_total = 101200121856
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=MacEnergyConsumption())
    mocker.patch.object(config, "load_kube_config", return_value=None)
    mocker.patch.object(Country, "get_current_country", return_value=location_name)
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=memory_total)
    cores_number = 2
    mocker.patch.object(HardwareInfo, "get_number_of_cores", return_value=cores_number)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=energy_usage)
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
    assert "energy_consumption_kubernetes_total" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "units:milliwatts",
    ] == metric.format_tags()

    milliwatts_expected = 4.9548
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == milliwatts_expected
    assert "energy_consumption_kubernetes_cpu" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "units:milliwatts",
    ] == metric.format_tags()

    milliwatts_expected = 1.8368
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == milliwatts_expected
    assert "energy_consumption_kubernetes_memory" == metric.name
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
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=MacEnergyConsumption())
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
    carbon_emission_kubernertes_generator = CarbonEmissionKubernetesGenerator(location=location, platform="Darwin")

    async_generator = carbon_emission_kubernertes_generator.generate()
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == carbon_usage_expected
    assert "carbon_emission_kubernetes_total" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "source:file",
        "units:co2mg",
    ] == metric.format_tags()

    carbon_usage_expected = 200.00

    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == carbon_usage_expected
    assert "carbon_emission_kubernetes_cpu" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "source:file",
        "units:co2mg",
    ] == metric.format_tags()

    carbon_usage_expected = 100.00

    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == carbon_usage_expected
    assert "carbon_emission_kubernetes_memory" == metric.name
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "source:file",
        "units:co2mg",
    ] == metric.format_tags()
