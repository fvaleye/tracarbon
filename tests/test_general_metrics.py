from datetime import datetime

import pytest
from kubernetes import config

import tracarbon.exporters.exporter as exporter_module
from tracarbon import RAPL
from tracarbon import CarbonEmission
from tracarbon import CarbonUsage
from tracarbon import EnergyConsumption
from tracarbon import EnergyUsage
from tracarbon import HardwareInfo
from tracarbon import Kubernetes
from tracarbon import LinuxEnergyConsumption
from tracarbon import MacEnergyConsumption
from tracarbon import UsageType
from tracarbon.exceptions import HardwareNoGPUDetectedException
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import CarbonEmissionKubernetesGenerator
from tracarbon.general_metrics import CarbonEmissionProcessGenerator
from tracarbon.general_metrics import EnergyConsumptionGenerator
from tracarbon.general_metrics import EnergyConsumptionKubernetesGenerator
from tracarbon.general_metrics import EnergyConsumptionProcessGenerator
from tracarbon.hardwares import Container
from tracarbon.hardwares import Pod
from tracarbon.hardwares import Processes
from tracarbon.hardwares import ProcessUsage
from tracarbon.hardwares import RAPLResult
from tracarbon.hardwares.gpu import AMDGPU
from tracarbon.hardwares.gpu import NvidiaGPU
from tracarbon.locations.country import Country


async def test_carbon_emission_metrics_preserve_names_and_tags(mocker):
    location = Country(name="fr", co2g_kwh=51.1)
    energy_usage = EnergyUsage(cpu_energy_usage=12.0, memory_energy_usage=4.0)
    mocker.patch.object(CarbonEmission, "get_energy_usage", return_value=energy_usage)
    generator = CarbonEmissionGenerator(location=location)

    metrics = [metric async for metric in generator.generate()]

    assert [metric.name for metric in metrics] == [
        "carbon_emission_host",
        "carbon_emission_cpu",
        "carbon_emission_memory",
        "carbon_emission_gpu",
    ]
    for metric in metrics:
        assert metric.tags[1:] == [
            Tag(key="location", value=location.name),
            Tag(key="source", value=location.co2g_kwh_source.value),
            Tag(key="units", value="co2g"),
        ]


async def test_energy_consumption_metrics_preserve_names_values_and_tags(mocker):
    location = Country(name="fr", co2g_kwh=51.1)
    energy_usage = EnergyUsage(
        host_energy_usage=16.0, cpu_energy_usage=12.0, memory_energy_usage=4.0, gpu_energy_usage=0.5
    )
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=energy_usage)
    generator = EnergyConsumptionGenerator(location=location, energy_consumption=MacEnergyConsumption())

    metrics = [metric async for metric in generator.generate()]

    assert [metric.name for metric in metrics] == [
        "energy_consumption_host",
        "energy_consumption_cpu",
        "energy_consumption_memory",
        "energy_consumption_gpu",
    ]
    assert {metric.name: await metric.value() for metric in metrics} == {
        "energy_consumption_host": 16.0,
        "energy_consumption_cpu": 12.0,
        "energy_consumption_memory": 4.0,
        "energy_consumption_gpu": 0.5,
    }
    for metric in metrics:
        assert metric.tags[1:] == [
            Tag(key="location", value=location.name),
            Tag(key="units", value="watts"),
        ]


async def test_energy_consumption_kubernetes_generator(mocker):
    location_name = "fr"
    memory_total = 101200121856
    energy_usage = EnergyUsage(
        cpu_energy_usage=12.0,
        memory_energy_usage=4.0,
        interval_joules={UsageType.CPU: 24.0, UsageType.MEMORY: 4.0},
    )
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
    milliwatts_expected = 6.8357
    mocker.patch.object(Kubernetes, "get_pods_usage", return_value=pods_usage)

    location = Country(name=location_name, co2g_kwh=51.1)
    energy_consumption_kubernertes_generator = EnergyConsumptionKubernetesGenerator(
        location=location, platform="Darwin"
    )

    async_generator = energy_consumption_kubernertes_generator.generate()
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == milliwatts_expected
    assert "energy_consumption_kubernetes_total" == metric.name
    assert metric.interval_joules == pytest.approx(0.0099096 + 46472 * 1024 / memory_total * 4)
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
    assert metric.interval_joules == pytest.approx(0.0099096)
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "units:milliwatts",
    ] == metric.format_tags()

    milliwatts_expected = 1.8809
    metric = await async_generator.__anext__()
    assert round(await metric.value(), 4) == milliwatts_expected
    assert "energy_consumption_kubernetes_memory" == metric.name
    assert metric.interval_joules == pytest.approx(46472 * 1024 / memory_total * 4)
    assert [
        f"pod_name:{pod_name}",
        f"pod_namespace:{namespace}",
        f"container_name:{container_name}",
        "platform:Darwin",
        "containers:kubernetes",
        f"location:{location_name}",
        "units:milliwatts",
    ] == metric.format_tags()


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
    carbon_usage_expected = 307.3742
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

    carbon_usage_expected = 107.3742

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


@pytest.mark.parametrize("generator_type", [CarbonEmissionGenerator, CarbonEmissionKubernetesGenerator])
def test_carbon_emission_generator_repr_hides_api_key(mocker, generator_type):
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=MacEnergyConsumption())
    mocker.patch.object(config, "load_kube_config", return_value=None)
    location = Country(name="fr", co2g_kwh=74.0, co2signal_api_key="SECRET_API_KEY")

    generator = generator_type(location=location, co2signal_api_key="SECRET_API_KEY")

    assert "SECRET_API_KEY" not in f"{generator} {generator!r}"


@pytest.mark.parametrize("cpu_watts,process_watts", [(12.0, 3.0), (None, None)])
async def test_energy_consumption_process_generator(mocker, cpu_watts, process_watts):
    mocker.patch.object(
        MacEnergyConsumption,
        "get_energy_usage",
        return_value=EnergyUsage(
            cpu_energy_usage=cpu_watts,
            interval_joules={UsageType.CPU: cpu_watts * 2} if cpu_watts is not None else {},
        ),
    )
    mocker.patch.object(
        Processes, "get_processes_usage", return_value=[ProcessUsage(pid=42, name="worker", cpu_usage=0.25)]
    )
    generator = EnergyConsumptionProcessGenerator(
        location=Country(name="fr", co2g_kwh=51.1),
        platform="Darwin",
        energy_consumption=MacEnergyConsumption(),
        processes=Processes(pids=[]),
    )

    metrics = [metric async for metric in generator.generate()]

    assert [metric.name for metric in metrics] == ["energy_consumption_process_cpu"]
    assert await metrics[0].value() == process_watts
    assert metrics[0].interval_joules == (process_watts * 2 if process_watts is not None else None)
    assert metrics[0].format_tags() == [
        "pid:42",
        "process_name:worker",
        "platform:Darwin",
        "location:fr",
        "units:watts",
    ]


async def test_carbon_emission_process_generator(mocker):
    mocker.patch.object(CarbonEmission, "get_co2_usage", return_value=CarbonUsage(cpu_carbon_usage=0.2))
    mocker.patch.object(
        Processes, "get_processes_usage", return_value=[ProcessUsage(pid=42, name="worker", cpu_usage=0.25)]
    )
    location = Country(name="fr", co2g_kwh=51.1)
    generator = CarbonEmissionProcessGenerator(location=location, platform="Darwin", processes=Processes(pids=[]))

    metrics = [metric async for metric in generator.generate()]

    assert [metric.name for metric in metrics] == ["carbon_emission_process_cpu"]
    assert await metrics[0].value() == pytest.approx(0.05)
    assert metrics[0].format_tags() == [
        "pid:42",
        "process_name:worker",
        "platform:Darwin",
        "location:fr",
        f"source:{location.co2g_kwh_source.value}",
        "units:co2g",
    ]


async def test_counter_readings_count_each_window_once_in_energy_and_carbon(mocker):
    late_starting_cpu_watts = [None, 4.2, 0.0, 4.1]

    class TwoSecondCounter(EnergyConsumption):
        watts: list

        async def get_energy_usage(self) -> EnergyUsage:
            watts = self.watts.pop(0)
            return EnergyUsage(
                host_energy_usage=None,
                cpu_energy_usage=watts,
                interval_joules={UsageType.CPU: watts * 2} if watts is not None else {},
            )

    location = Country(name="fr", co2g_kwh=41.44)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=41.44)
    carbon_emission = CarbonEmission(
        location=location, energy_consumption=TwoSecondCounter(watts=list(late_starting_cpu_watts))
    )
    exporter = StdoutExporter(
        metric_generators=[
            EnergyConsumptionGenerator(
                location=location, energy_consumption=TwoSecondCounter(watts=list(late_starting_cpu_watts))
            ),
            CarbonEmissionGenerator(location=location, carbon_emission=carbon_emission),
        ]
    )
    clock = mocker.patch.object(exporter_module, "time")

    for collected_at in (0.0, 3.7, 9.1, 20.0):
        clock.monotonic.return_value = collected_at
        await exporter._launch_all()

    energy_wh = exporter.metric_report["energy_consumption_cpu"].total
    assert energy_wh == pytest.approx(16.6 / 3600)
    assert exporter.metric_report["carbon_emission_cpu"].total == pytest.approx(energy_wh / 1000 * 41.44)


@pytest.mark.parametrize(
    "gpu_joules,gpu_seconds,expected_joules",
    [
        (None, 0.1, {"host": 12, "cpu": 10, "memory": 2}),
        (3, 0.1, {"host": 12, "cpu": 7, "memory": 2, "gpu": 3}),
        (12, 0.05, {"host": 12, "memory": 2, "gpu": 12}),
        (10, 0.1, {"host": 12, "cpu": 0, "memory": 2, "gpu": 10}),
    ],
)
async def test_rapl_domains_keep_their_own_intervals_through_the_report(
    mocker, gpu_joules, gpu_seconds, expected_joules
):
    def reading(name, joules, seconds):
        return RAPLResult(
            name=name,
            energy_uj=joules * 1_000_000,
            max_energy_uj=100_000_000,
            timestamp=datetime(2026, 1, 1),
            monotonic_time=seconds,
        )

    previous = [reading(":0-package-0", 0, 0), reading(":0:0-dram", 0, 0)]
    current = [reading(":0-package-0", 10, 0.1), reading(":0:0-dram", 2, 0.4)]
    if gpu_joules is not None:
        previous.append(reading(":0:1-uncore", 0, 0))
        current.append(reading(":0:1-uncore", gpu_joules, gpu_seconds))
    mocker.patch.object(RAPL, "get_rapl_power_usage", return_value=current)
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=True)
    for gpu_type in (NvidiaGPU, AMDGPU):
        mocker.patch.object(gpu_type, "get_gpu_power_usage", side_effect=HardwareNoGPUDetectedException("no GPU"))
    location = Country(name="fr", co2g_kwh=100)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=100)

    def sensor():
        return LinuxEnergyConsumption(rapl=RAPL(rapl_results={r.name: r for r in previous}))

    exporter = StdoutExporter(
        metric_generators=[
            EnergyConsumptionGenerator(location=location, energy_consumption=sensor()),
            CarbonEmissionGenerator(
                location=location,
                carbon_emission=CarbonEmission(
                    location=location,
                    energy_consumption=sensor(),
                ),
            ),
        ]
    )
    await exporter._launch_all()

    assert {name: report.total * 3600 for name, report in exporter.metric_report.items()} == pytest.approx(
        {f"energy_consumption_{component}": joules for component, joules in expected_joules.items()}
        | {f"carbon_emission_{component}": joules / 1000 * 100 for component, joules in expected_joules.items()}
    )
