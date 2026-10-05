import asyncio
import contextlib
import os
import shlex
import signal
import subprocess
import time
from collections import namedtuple
from operator import attrgetter
from threading import Event

import psutil
import pytest
import requests
from pytest_mock import MockerFixture

from tracarbon import AMDRAPL
from tracarbon import RAPL
from tracarbon import AWSEC2EnergyConsumption
from tracarbon import Country
from tracarbon import EnergyConsumption
from tracarbon import LinuxEnergyConsumption
from tracarbon import TracarbonException
from tracarbon.exceptions import AWSSensorException
from tracarbon.exceptions import AzureSensorException
from tracarbon.exceptions import GCPSensorException
from tracarbon.exceptions import HardwareIOReportException
from tracarbon.exceptions import HardwareNoGPUDetectedException
from tracarbon.hardwares import EnergyUsage
from tracarbon.hardwares import HardwareInfo
from tracarbon.hardwares import WindowsEnergyConsumption
from tracarbon.hardwares.cloud_providers import AWS
from tracarbon.hardwares.cloud_providers import GCP
from tracarbon.hardwares.cloud_providers import Azure
from tracarbon.hardwares.cloud_providers import CloudProviders
from tracarbon.hardwares.gpu import AMDGPU
from tracarbon.hardwares.gpu import AppleSiliconPowerMetrics
from tracarbon.hardwares.gpu import GPUInfo
from tracarbon.hardwares.gpu import NvidiaGPU
from tracarbon.hardwares.ioreport import IOReportEnergy
from tracarbon.hardwares.sensors import AzureEnergyConsumption
from tracarbon.hardwares.sensors import GCPEnergyConsumption
from tracarbon.hardwares.sensors import MacEnergyConsumption
from tracarbon.locations import AzureLocation


@pytest.fixture(autouse=True)
def without_the_energy_counters(mocker):
    """
    Keep the Mac sensor off the energy counters unless a test asks for them, so that the fallbacks
    are exercised the same way on hardware that counts energy and on hardware that does not.
    """
    mocker.patch.object(IOReportEnergy, "is_available", return_value=False)


@pytest.mark.darwin
def test_get_platform_should_return_the_platform_energy_consumption_mac():
    energy_consumption = EnergyConsumption.from_platform()

    assert (
        energy_consumption.shell_command
        == """ioreg -rw0 -a -c AppleSmartBattery | plutil -extract '0.BatteryData.SystemPower' raw -"""
    )
    assert energy_consumption.init is False


@pytest.mark.asyncio
async def test_mac_energy_consumption_with_powermetrics(mocker):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        return_value=(5.2, 1.8, 0.3),
    )

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.cpu_energy_usage == 5.2
    assert energy_usage.gpu_energy_usage == 1.8
    assert abs(energy_usage.host_energy_usage - 7.3) < 0.01


@pytest.mark.asyncio
async def test_mac_energy_consumption_powermetrics_no_ane(mocker):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        return_value=(4.0, 2.0, None),
    )

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.cpu_energy_usage == 4.0
    assert energy_usage.gpu_energy_usage == 2.0
    assert abs(energy_usage.host_energy_usage - 6.0) < 0.01


@pytest.mark.parametrize(
    ("reported_power", "expected_watts"),
    [
        (b"25.500000", 25.5),
        (b"3051", 3.051),
        (b"1101610469", 21.155221939086914),
    ],
    ids=["watts", "milliwatts", "encoded-float"],
)
@pytest.mark.asyncio
async def test_mac_energy_consumption_fallback_to_ioreg(mocker, reported_power, expected_watts):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        side_effect=Exception("powermetrics not available"),
    )
    mocker.patch(
        "tracarbon.hardwares.sensors.asyncio.create_subprocess_shell",
        return_value=mocker.AsyncMock(communicate=mocker.AsyncMock(return_value=(reported_power, None))),
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=3.5)

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage == pytest.approx(expected_watts)
    assert energy_usage.gpu_energy_usage == 3.5
    assert energy_usage.cpu_energy_usage is None


@pytest.mark.asyncio
async def test_mac_energy_consumption_ioreg_parse_failure_reports_unknown_power(mocker):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        side_effect=Exception("powermetrics not available"),
    )
    property_list_error = b"<stdin>: Property List error: Cannot parse a NULL or zero-length data\n"
    mocker.patch(
        "tracarbon.hardwares.sensors.asyncio.create_subprocess_shell",
        return_value=mocker.AsyncMock(communicate=mocker.AsyncMock(return_value=(property_list_error, None))),
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage is None
    assert energy_usage.gpu_energy_usage is None


def test_get_platform_should_raise_exception():
    with pytest.raises(TracarbonException) as exception:
        EnergyConsumption.from_platform(platform="unknown")
    assert exception.value.args[0] == "This unknown hardware is not yet implemented."


def test_is_ec2_should_return_false_on_exception():
    assert AWS.is_ec2() is False


@pytest.mark.asyncio
async def test_aws_sensor_with_gpu_should_return_energy_consumption(mocker):
    aws_ec2_sensor = AWSEC2EnergyConsumption(instance_type="p2.8xlarge")

    assert aws_ec2_sensor.cpu_idle == 15.55
    assert aws_ec2_sensor.cpu_at_10 == 44.38
    assert aws_ec2_sensor.cpu_at_50 == 91.28
    assert aws_ec2_sensor.cpu_at_100 == 124.95
    assert aws_ec2_sensor.memory_idle == 97.6
    assert aws_ec2_sensor.memory_at_10 == 146.4
    assert aws_ec2_sensor.memory_at_50 == 195.2
    assert aws_ec2_sensor.memory_at_100 == 292.8
    assert aws_ec2_sensor.has_gpu is True
    assert aws_ec2_sensor.delta_full_machine == 25.8

    mocker.patch.object(HardwareInfo, "get_cpu_usage_since", return_value=(50, None))
    gpu_power_usage = 1805.4
    mocker.patch.object(HardwareInfo, "get_gpu_power_usage", return_value=gpu_power_usage)
    value_expected = (
        aws_ec2_sensor.cpu_at_50 + aws_ec2_sensor.memory_at_50 + aws_ec2_sensor.delta_full_machine + gpu_power_usage
    )

    energy_usage = await aws_ec2_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage == value_expected


@pytest.mark.asyncio
async def test_aws_sensor_without_gpu_should_return_energy_consumption(mocker):
    aws_ec2_sensor = AWSEC2EnergyConsumption(instance_type="m5.8xlarge")

    assert aws_ec2_sensor.cpu_idle == 19.29
    assert aws_ec2_sensor.cpu_at_10 == 48.88
    assert aws_ec2_sensor.cpu_at_50 == 114.57
    assert aws_ec2_sensor.cpu_at_100 == 159.33
    assert aws_ec2_sensor.memory_idle == 19.27
    assert aws_ec2_sensor.memory_at_10 == 30.8
    assert aws_ec2_sensor.memory_at_50 == 79.37
    assert aws_ec2_sensor.memory_at_100 == 127.94
    assert aws_ec2_sensor.has_gpu is False
    assert aws_ec2_sensor.delta_full_machine == 32.0

    mocker.patch.object(HardwareInfo, "get_cpu_usage_since", return_value=(50, None))
    value_expected = aws_ec2_sensor.cpu_at_50 + aws_ec2_sensor.memory_at_50 + aws_ec2_sensor.delta_full_machine

    energy_usage = await aws_ec2_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage == value_expected


@pytest.mark.parametrize(
    ("cpu_usage", "cpu_watts", "memory_watts"),
    [(0.0, 1.21, 1.2), (49.0, 7.05725, 4.884), (100.0, 9.96, 8.0)],
)
@pytest.mark.asyncio
async def test_aws_sensor_interpolates_the_cpu_and_memory_power_at_the_cpu_load(
    mocker, cpu_usage, cpu_watts, memory_watts
):
    aws_ec2_sensor = AWSEC2EnergyConsumption(instance_type="m5.large")
    mocker.patch.object(HardwareInfo, "get_cpu_usage_since", return_value=(cpu_usage, None))
    mocker.patch.object(HardwareInfo, "get_memory_usage", return_value=20.0)

    energy_usage = await aws_ec2_sensor.get_energy_usage()

    assert energy_usage.cpu_energy_usage == pytest.approx(cpu_watts)
    assert energy_usage.memory_energy_usage == pytest.approx(memory_watts)
    assert energy_usage.host_energy_usage == pytest.approx(cpu_watts + memory_watts + 2.0)


@pytest.mark.parametrize(
    ("sensor_type", "instance_type", "exception_class"),
    [
        (AWSEC2EnergyConsumption, "m7i.large", AWSSensorException),
        (GCPEnergyConsumption, "c4a-standard-4", GCPSensorException),
        (GCPEnergyConsumption, "Standard_n2-standard-4", GCPSensorException),
        (AzureEnergyConsumption, "Standard_D4s_v5", AzureSensorException),
    ],
    ids=["aws", "gcp", "gcp-with-azure-prefix", "azure"],
)
def test_cloud_sensors_reject_an_unknown_instance_type(sensor_type, instance_type, exception_class):
    with pytest.raises(exception_class, match="is missing from the") as exception:
        sensor_type(instance_type=instance_type)
    assert f"[{instance_type}]" in str(exception.value)


@pytest.mark.parametrize("head_status", [200, 401])
def test_is_ec2_should_return_true_with_valid_metadata(mocker: MockerFixture, head_status: int) -> None:
    response = requests.Response()
    response.status_code = head_status
    mocker.patch.object(requests, "head", return_value=response)
    metadata = mocker.patch("tracarbon.hardwares.cloud_providers.ec2_metadata")
    metadata.instance_identity_document = {"region": "eu-west-1", "instanceType": "m5.large"}

    assert AWS.is_ec2() is True


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"region": "eu-west-1"},
        {"instanceType": "m5.large"},
        {"region": "eu-west-1", "instanceType": None},
        {"region": 123, "instanceType": "m5.large"},
        {"region": "", "instanceType": "m5.large"},
        {"region": "eu-west-1", "instanceType": " "},
        [],
        None,
    ],
)
def test_is_ec2_rejects_invalid_metadata(mocker: MockerFixture, document: object) -> None:
    response = requests.Response()
    response.status_code = 200
    mocker.patch.object(requests, "head", return_value=response)
    metadata = mocker.patch("tracarbon.hardwares.cloud_providers.ec2_metadata")
    metadata.instance_identity_document = document

    assert AWS.is_ec2() is False


@pytest.mark.parametrize("provider", ["gcp", "azure", None])
def test_cloud_provider_auto_detect_continues_after_aws_metadata_failure(
    mocker: MockerFixture, provider: str | None
) -> None:
    CloudProviders.auto_detect.cache_clear()
    response = requests.Response()
    response.status_code = 400
    mocker.patch.object(requests, "head", return_value=response)
    metadata = mocker.patch("tracarbon.hardwares.cloud_providers.ec2_metadata")
    for attribute in ("instance_identity_document", "region"):
        setattr(type(metadata), attribute, mocker.PropertyMock(side_effect=requests.HTTPError("HTTP 400")))

    def get_metadata(url: str, **kwargs: object) -> requests.Response:
        response = requests.Response()
        response.status_code = 404
        if provider == "gcp" and url.startswith(GCP.METADATA_URL):
            response.status_code = 200
            response._content = (
                b"projects/123456/machineTypes/n2-standard-4"
                if url.endswith("machine-type")
                else b"projects/123456/zones/us-central1-a"
            )
        elif provider == "azure" and url.startswith(Azure.IMDS_URL):
            response.status_code = 200
            response._content = b'{"compute":{"vmSize":"Standard_D2s_v3","location":"eastus"}}'
        return response

    mocker.patch.object(requests, "get", side_effect=get_metadata)
    try:
        result = CloudProviders.auto_detect()
        if provider == "gcp":
            assert result == GCP(instance_type="n2-standard-4", region_name="us-central1")
        elif provider == "azure":
            assert result == Azure(instance_type="Standard_D2s_v3", region_name="eastus")
        else:
            assert result is None
    finally:
        CloudProviders.auto_detect.cache_clear()


def test_cloud_provider_auto_detect_reuses_aws_identity_document(mocker: MockerFixture) -> None:
    CloudProviders.auto_detect.cache_clear()
    response = requests.Response()
    response.status_code = 401
    mocker.patch.object(requests, "head", return_value=response)
    metadata = mocker.patch("tracarbon.hardwares.cloud_providers.ec2_metadata")
    metadata.instance_identity_document = {"region": "eu-west-1", "instanceType": "m5.large"}
    try:
        result = CloudProviders.auto_detect()
        assert result == AWS(instance_type="m5.large", region_name="eu-west-1")
        assert CloudProviders.auto_detect() is result
    finally:
        CloudProviders.auto_detect.cache_clear()


def test_cloud_provider_auto_detect_caches_negative_result(mocker):
    CloudProviders.auto_detect.cache_clear()
    is_ec2 = mocker.patch.object(AWS, "is_ec2", return_value=False)
    is_gcp = mocker.patch.object(GCP, "is_gcp", return_value=False)
    is_azure = mocker.patch.object(Azure, "is_azure", return_value=False)

    assert CloudProviders.auto_detect() is None
    assert CloudProviders.auto_detect() is None
    assert CloudProviders.is_running_on_cloud_provider() is False

    is_ec2.assert_called_once()
    is_gcp.assert_called_once()
    is_azure.assert_called_once()
    CloudProviders.auto_detect.cache_clear()


@pytest.mark.asyncio
async def test_get_platform_should_return_the_platform_energy_consumption_linux_error(
    mocker,
):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=False)
    mocker.patch.object(AMDRAPL, "is_amd_rapl_compatible", return_value=False)
    mocker.patch.object(NvidiaGPU, "launch_shell_command", side_effect=HardwareNoGPUDetectedException("no GPU"))
    mocker.patch.object(AMDGPU, "launch_shell_command", side_effect=HardwareNoGPUDetectedException("no GPU"))

    with pytest.raises(TracarbonException) as exception:
        await LinuxEnergyConsumption().get_energy_usage()
    assert "No supported RAPL interface found" in exception.value.args[0]


@pytest.mark.asyncio
async def test_linux_reads_the_gpu_when_no_rapl_counter_is_readable(mocker):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=False)
    mocker.patch.object(AMDRAPL, "is_amd_rapl_compatible", return_value=False)
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(b"250.00 W", 0))
    linux_energy_consumption = LinuxEnergyConsumption()

    first_energy_usage = await linux_energy_consumption.get_energy_usage()
    second_energy_usage = await linux_energy_consumption.get_energy_usage()

    assert first_energy_usage == second_energy_usage == EnergyUsage(host_energy_usage=None, gpu_energy_usage=250.0)


@pytest.mark.asyncio
async def test_get_platform_should_return_the_platform_energy_consumption_linux(mocker):
    energy_usage = EnergyUsage(host_energy_usage=1.8)
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=True)
    mocker.patch.object(
        RAPL,
        "get_energy_report",
        return_value=energy_usage,
    )

    results = await LinuxEnergyConsumption().get_energy_usage()

    assert results == energy_usage


@pytest.mark.asyncio
async def test_linux_adds_nvidia_power_to_amd_rapl_when_powercap_unavailable(mocker):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=False)
    mocker.patch.object(AMDRAPL, "is_amd_rapl_compatible", return_value=True)
    mocker.patch.object(AMDRAPL, "get_energy_report", return_value=EnergyUsage(host_energy_usage=100.0))
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(b"300 W", 0))

    results = await LinuxEnergyConsumption().get_energy_usage()

    assert results.host_energy_usage == 400.0
    assert results.gpu_energy_usage == 300.0


@pytest.mark.parametrize(
    ("rapl_gpu", "nvidia_output", "expected_host", "expected_gpu"),
    [
        (None, b"300 W", 400.0, 300.0),
        (15.0, b"100 W\n200 W", 400.0, 315.0),
        (15.0, b"[N/A]", 100.0, 15.0),
        (15.0, b"-1 W", 100.0, 15.0),
        (15.0, b"nan W", 100.0, 15.0),
        (15.0, b"inf W", 100.0, 15.0),
        (None, b"0 W", 100.0, 0.0),
        (15.0, b"0 W", 100.0, 15.0),
    ],
)
@pytest.mark.asyncio
async def test_linux_adds_nvidia_power_once_and_preserves_rapl_gpu(
    mocker, rapl_gpu, nvidia_output, expected_host, expected_gpu
):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=True)
    mocker.patch.object(
        RAPL,
        "get_energy_report",
        return_value=EnergyUsage(host_energy_usage=100.0, gpu_energy_usage=rapl_gpu),
    )
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(nvidia_output, 0))
    mocker.patch.object(AMDGPU, "launch_shell_command", return_value=(b"", 1))

    energy_usage = await LinuxEnergyConsumption().get_energy_usage()

    assert energy_usage.host_energy_usage == expected_host
    assert energy_usage.gpu_energy_usage == expected_gpu


@pytest.mark.parametrize("rapl_gpu", [None, 15.0])
@pytest.mark.asyncio
async def test_linux_keeps_amd_fallback_out_of_rapl_host_power(mocker, rapl_gpu):
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=True)
    mocker.patch.object(
        RAPL,
        "get_energy_report",
        return_value=EnergyUsage(host_energy_usage=100.0, gpu_energy_usage=rapl_gpu),
    )
    mocker.patch.object(NvidiaGPU, "launch_shell_command", side_effect=subprocess.TimeoutExpired("nvidia-smi", 10))
    mocker.patch.object(
        AMDGPU,
        "launch_shell_command",
        return_value=(b"GPU[0] : Average Graphics Package Power (W): 45.0", 0),
    )

    energy_usage = await LinuxEnergyConsumption().get_energy_usage()

    assert energy_usage.host_energy_usage == 100.0
    assert energy_usage.gpu_energy_usage == 45.0


@pytest.mark.asyncio
@pytest.mark.parametrize("gpu_power", [0.0, 50.0])
async def test_windows_reports_gpu_power_without_inventing_host_power(mocker, gpu_power):
    mocker.patch.object(NvidiaGPU, "get_gpu_power_usage", return_value=gpu_power)

    energy = await WindowsEnergyConsumption().get_energy_usage()

    assert energy.host_energy_usage is None
    assert energy.cpu_energy_usage is None
    assert energy.memory_energy_usage is None
    assert energy.gpu_energy_usage == gpu_power


def test_is_gcp_should_return_false_on_exception():
    assert GCP.is_gcp() is False


def test_is_gcp_should_return_true(mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mocker.patch.object(requests, "get", return_value=mock_response)

    assert GCP.is_gcp() is True


def test_gcp_from_metadata(mocker):
    mock_machine_response = mocker.Mock()
    mock_machine_response.text = "projects/123456/machineTypes/n2-standard-4"

    mock_zone_response = mocker.Mock()
    mock_zone_response.text = "projects/123456/zones/us-central1-a"

    mocker.patch.object(
        requests,
        "get",
        side_effect=[mock_machine_response, mock_zone_response],
    )

    gcp = GCP.from_metadata()

    assert gcp.instance_type == "n2-standard-4"
    assert gcp.region_name == "us-central1"


@pytest.mark.asyncio
async def test_gcp_sensor_returns_energy_consumption_for_a_newer_machine_series(mocker):
    gcp_sensor = GCPEnergyConsumption(instance_type="c4-standard-2")

    assert gcp_sensor.vcpus == 2.0
    assert gcp_sensor.memory_gb == 7.0

    mocker.patch.object(HardwareInfo, "get_cpu_usage_since", return_value=(50, None))
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)

    energy_usage = await gcp_sensor.get_energy_usage()

    assert energy_usage.cpu_energy_usage == pytest.approx(5.195)
    assert energy_usage.host_energy_usage == pytest.approx(5.195)


def test_is_azure_should_return_false_on_exception():
    assert Azure.is_azure() is False


def test_is_azure_should_return_true(mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mocker.patch.object(requests, "get", return_value=mock_response)

    assert Azure.is_azure() is True


def test_azure_from_metadata(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"compute": {"vmSize": "Standard_D2s_v3", "location": "eastus"}}
    mocker.patch.object(requests, "get", return_value=mock_response)

    azure = Azure.from_metadata()

    assert azure.instance_type == "Standard_D2s_v3"
    assert azure.region_name == "eastus"


@pytest.mark.asyncio
async def test_azure_sensor_should_return_energy_consumption(mocker):
    azure_sensor = AzureEnergyConsumption(instance_type="D2 v3")

    assert azure_sensor.vcpus == 2.0
    assert azure_sensor.memory_gb == 8.0
    assert azure_sensor.min_watts > 0
    assert azure_sensor.max_watts > azure_sensor.min_watts

    mocker.patch.object(HardwareInfo, "get_cpu_usage_since", return_value=(50, None))
    from tracarbon.hardwares.gpu import GPUInfo

    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)

    energy_usage = await azure_sensor.get_energy_usage()

    expected_power = azure_sensor.min_watts + (azure_sensor.max_watts - azure_sensor.min_watts) * 0.5
    assert abs(energy_usage.host_energy_usage - expected_power) < 0.01


@pytest.mark.parametrize(
    ("vm_size", "location", "instance_type", "region_name"),
    [
        ("Standard_D2s_v3", "westeurope", "D2s v3", "West Europe"),
        ("Standard_B2ms", "eastus", "B2MS", "East US"),
        ("standard_b2ms", "EastUS", "B2MS", "East US"),
        ("Standard_NC4as_T4_v3", "westus3", "NC4as T4 v3", "West US 3"),
    ],
)
def test_azure_metadata_names_find_the_instance_and_the_region(mocker, vm_size, location, instance_type, region_name):
    mocker.patch.object(AWS, "is_ec2", return_value=False)
    mocker.patch.object(GCP, "is_gcp", return_value=False)
    imds_response = mocker.Mock(status_code=200)
    imds_response.json.return_value = {"compute": {"vmSize": vm_size, "location": location}}
    mocker.patch.object(requests, "get", return_value=imds_response)
    CloudProviders.auto_detect.cache_clear()
    try:
        energy_consumption = EnergyConsumption.from_platform()
        country = Country.get_location()
    finally:
        CloudProviders.auto_detect.cache_clear()

    assert energy_consumption == AzureEnergyConsumption(instance_type=instance_type)
    assert country.co2g_kwh == AzureLocation(region_name=region_name).co2g_kwh


@pytest.mark.parametrize(
    ("new_sensor", "idle_watts", "full_load_watts"),
    [
        (lambda: GCPEnergyConsumption(instance_type="n2-standard-4"), attrgetter("min_watts"), attrgetter("max_watts")),
        (lambda: AWSEC2EnergyConsumption(instance_type="m5.large"), attrgetter("cpu_idle"), attrgetter("cpu_at_100")),
    ],
    ids=["gcp", "aws"],
)
@pytest.mark.asyncio
async def test_cloud_sensors_each_measure_the_cpu_load_since_their_own_previous_reading(
    mocker, new_sensor, idle_watts, full_load_watts
):
    CPUTimes = namedtuple("CPUTimes", "user nice system idle")
    cpu_times = mocker.patch.object(
        psutil, "cpu_times", return_value=CPUTimes(user=0.0, nice=0.0, system=0.0, idle=100.0)
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)
    energy_sensor, carbon_sensor = new_sensor(), new_sensor()

    first_readings = [await sensor.get_energy_usage() for sensor in (energy_sensor, carbon_sensor)]
    cpu_times.return_value = CPUTimes(user=100.0, nice=0.0, system=0.0, idle=100.0)
    next_readings = [
        await asyncio.to_thread(asyncio.run, sensor.get_energy_usage()) for sensor in (energy_sensor, carbon_sensor)
    ]

    assert [reading.cpu_energy_usage for reading in first_readings] == [idle_watts(energy_sensor)] * 2
    assert [reading.cpu_energy_usage for reading in next_readings] == [full_load_watts(energy_sensor)] * 2


@pytest.mark.asyncio
async def test_mac_energy_consumption_reads_the_adapter_when_no_system_power_is_reported(mocker):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        side_effect=HardwareNoGPUDetectedException("powermetrics failed to run."),
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)
    read_power = mocker.patch.object(MacEnergyConsumption, "_read_power", side_effect=[None, 30.0])

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage == 30.0
    assert read_power.call_count == 2
    assert "AdapterPower" in read_power.call_args.args[0]


@pytest.mark.asyncio
async def test_mac_energy_consumption_reads_system_load_when_legacy_keys_are_missing(mocker):
    mocker.patch.object(AppleSiliconPowerMetrics, "get_power_breakdown", return_value=(None, None, None))
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)
    read_power = mocker.patch.object(MacEnergyConsumption, "_read_power", side_effect=[None, None, 45.964])

    energy_usage = await MacEnergyConsumption().get_energy_usage()

    assert energy_usage.host_energy_usage == 45.964
    assert energy_usage.cpu_energy_usage is None
    assert read_power.call_count == 3
    assert "PowerTelemetryData.SystemLoad" in read_power.call_args.args[0]


@pytest.mark.asyncio
async def test_mac_energy_consumption_reports_unknown_power_when_ioreg_reports_no_key(mocker):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        side_effect=HardwareNoGPUDetectedException("powermetrics failed to run."),
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)
    mocker.patch.object(MacEnergyConsumption, "_read_power", return_value=None)

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage is None


@pytest.mark.parametrize("timeout", [False, True])
@pytest.mark.asyncio
async def test_ioreg_warns_once_per_failure_streak_and_recovers(mocker, caplog, timeout):
    read_power = mocker.patch.object(MacEnergyConsumption, "_read_power", return_value=None)
    if timeout:
        read_power.side_effect = asyncio.TimeoutError
    sensor = MacEnergyConsumption()

    missing_readings = [await sensor._read_ioreg_power() for _ in range(5)]
    read_power.side_effect = None
    read_power.return_value = 30.0
    recovered_reading = await sensor._read_ioreg_power()
    read_power.return_value = None
    await sensor._read_ioreg_power()

    assert missing_readings == [None] * 5
    assert recovered_reading == 30.0
    failures = [record for record in caplog.records if "unknown" in record.message]
    assert [record.levelname for record in failures] == ["WARNING", "DEBUG", "DEBUG", "DEBUG", "DEBUG", "WARNING"]


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
@pytest.mark.parametrize(
    ("cancel_reading", "during_creation"),
    [(False, False), (True, False), (True, True)],
    ids=["timeout", "cancellation", "creation-cancellation"],
)
async def test_stopping_ioreg_stops_pipeline_children(mocker, monkeypatch, tmp_path, cancel_reading, during_creation):
    launched_commands = mocker.spy(asyncio, "create_subprocess_shell")
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        side_effect=HardwareNoGPUDetectedException("powermetrics unavailable"),
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)
    monkeypatch.setattr("tracarbon.hardwares.sensors.PROBE_TIMEOUT_SECONDS", 30 if cancel_reading else 0.5)
    pid_files = [tmp_path / "ioreg.pid", tmp_path / "plutil.pid"]
    commands = []
    for pid_file in pid_files:
        command = f"echo $$ > {shlex.quote(str(pid_file))}; exec sleep 30"
        commands.append(f"sh -c {shlex.quote(command)}")
    sensor = MacEnergyConsumption(shell_command=" | ".join(commands), adapter_shell_command="printf ''")
    creation_can_finish = asyncio.Event()
    if during_creation:
        loop = asyncio.get_running_loop()
        connect_read_pipe = loop.connect_read_pipe

        async def connect_after_cancellation(*args, **kwargs):
            await creation_can_finish.wait()
            return await connect_read_pipe(*args, **kwargs)

        mocker.patch.object(loop, "connect_read_pipe", side_effect=connect_after_cancellation)

    started_at = time.monotonic()
    reading = asyncio.create_task(sensor.get_energy_usage())
    try:
        if cancel_reading:
            while not all(pid_file.exists() for pid_file in pid_files):
                assert time.monotonic() - started_at < 3, "Pipeline did not start"
                await asyncio.sleep(0.01)
            reading.cancel()
            creation_can_finish.set()
            with pytest.raises(asyncio.CancelledError):
                await reading
        else:
            energy_usage = await reading
            assert energy_usage.host_energy_usage is None
        assert time.monotonic() - started_at < 3
        assert launched_commands.call_count == 1
        for pid_file in pid_files:
            probe_pid = int(pid_file.read_text())
            for _ in range(100):
                try:
                    if psutil.Process(probe_pid).status() == psutil.STATUS_ZOMBIE:
                        break
                except psutil.NoSuchProcess:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail(f"Pipeline child {probe_pid} survived stopping the reading")
    finally:
        creation_can_finish.set()
        reading.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reading
        for pid_file in pid_files:
            if pid_file.exists():
                with contextlib.suppress(ProcessLookupError):
                    os.kill(int(pid_file.read_text()), signal.SIGKILL)


@pytest.mark.asyncio
async def test_mac_energy_consumption_prefers_the_energy_counters(mocker):
    counted = EnergyUsage(host_energy_usage=8.0, cpu_energy_usage=5.0, gpu_energy_usage=2.0, memory_energy_usage=1.0)
    mocker.patch.object(IOReportEnergy, "is_available", return_value=True)
    mocker.patch.object(IOReportEnergy, "__init__", return_value=None)
    mocker.patch.object(IOReportEnergy, "get_energy_report", return_value=counted)
    powermetrics = mocker.patch("tracarbon.hardwares.sensors.AppleSiliconPowerMetrics")

    energy_usage = await MacEnergyConsumption().get_energy_usage()

    assert energy_usage == counted
    powermetrics.get_power_breakdown.assert_not_called()


@pytest.mark.asyncio
async def test_mac_energy_consumption_falls_back_when_the_counters_cannot_be_read(mocker):
    mocker.patch.object(IOReportEnergy, "is_available", return_value=True)
    mocker.patch.object(IOReportEnergy, "__init__", return_value=None)
    mocker.patch.object(
        IOReportEnergy, "get_energy_report", side_effect=HardwareIOReportException("no energy between the samples")
    )
    mocker.patch.object(MacEnergyConsumption, "_read_power", return_value=30.0)
    mocker.patch(
        "tracarbon.hardwares.sensors.AppleSiliconPowerMetrics.get_power_breakdown",
        side_effect=HardwareIOReportException("powermetrics failed to run."),
    )
    mocker.patch("tracarbon.hardwares.sensors.GPUInfo.get_gpu_power_usage_or_none", return_value=None)

    energy_usage = await MacEnergyConsumption().get_energy_usage()

    assert energy_usage.host_energy_usage == 30.0


@pytest.mark.parametrize("gpu_watts", [0.0, 2.0])
@pytest.mark.parametrize("host_watts", [None, 30.0])
@pytest.mark.asyncio
async def test_partial_energy_counters_use_ioreg_and_preserve_gpu(mocker, gpu_watts, host_watts):
    counted = EnergyUsage(host_energy_usage=None, gpu_energy_usage=gpu_watts)
    mocker.patch.object(MacEnergyConsumption, "_read_energy_counters", return_value=counted)
    mocker.patch.object(
        AppleSiliconPowerMetrics, "get_power_breakdown", side_effect=HardwareNoGPUDetectedException("no permission")
    )
    mocker.patch.object(MacEnergyConsumption, "_read_power", return_value=host_watts)
    gpu_probe = mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none")

    report = await MacEnergyConsumption().get_energy_usage()

    assert report.host_energy_usage == host_watts
    assert report.gpu_energy_usage == gpu_watts
    assert report.cpu_energy_usage is None
    assert report.memory_energy_usage is None
    gpu_probe.assert_not_called()


@pytest.mark.parametrize("powermetrics_gpu_watts", [None, 0.0, 3.0])
@pytest.mark.parametrize("gpu_watts", [0.0, 0.2])
@pytest.mark.asyncio
async def test_partial_energy_counters_fall_back_to_powermetrics(mocker, powermetrics_gpu_watts, gpu_watts):
    counted = EnergyUsage(host_energy_usage=None, gpu_energy_usage=gpu_watts)
    mocker.patch.object(MacEnergyConsumption, "_read_energy_counters", return_value=counted)
    mocker.patch.object(
        AppleSiliconPowerMetrics, "get_power_breakdown", return_value=(5.0, powermetrics_gpu_watts, 0.5)
    )
    ioreg_probe = mocker.patch.object(MacEnergyConsumption, "_read_power")

    report = await MacEnergyConsumption().get_energy_usage()

    assert report.cpu_energy_usage == 5.0
    assert report.gpu_energy_usage == gpu_watts
    assert report.host_energy_usage == 5.5 + (powermetrics_gpu_watts or 0.0)
    ioreg_probe.assert_not_called()


@pytest.mark.asyncio
async def test_powermetrics_gpu_only_uses_ioreg_for_host(mocker):
    mocker.patch.object(AppleSiliconPowerMetrics, "get_power_breakdown", return_value=(None, 2.0, None))
    mocker.patch.object(MacEnergyConsumption, "_read_power", return_value=30.0)
    gpu_probe = mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none")

    report = await MacEnergyConsumption().get_energy_usage()

    assert report.host_energy_usage == 30.0
    assert report.gpu_energy_usage == 2.0
    assert report.cpu_energy_usage is None
    gpu_probe.assert_not_called()


@pytest.mark.parametrize("probe", ["powermetrics", "gpu"])
@pytest.mark.asyncio
async def test_mac_power_probes_leave_the_event_loop_responsive(mocker, probe):
    released = Event()
    loop_ran = []

    def read_power():
        loop_ran.append(released.wait(timeout=1))
        return (5.0, 2.0, None) if probe == "powermetrics" else 2.0

    mocker.patch.object(MacEnergyConsumption, "_read_power", return_value=20.0)
    mocker.patch.object(AppleSiliconPowerMetrics, "get_power_breakdown", return_value=(None, None, None))
    target = AppleSiliconPowerMetrics if probe == "powermetrics" else GPUInfo
    method = "get_power_breakdown" if probe == "powermetrics" else "get_gpu_power_usage_or_none"
    mocker.patch.object(target, method, side_effect=read_power)
    callback = asyncio.get_running_loop().call_later(0.01, released.set)

    try:
        report = await MacEnergyConsumption().get_energy_usage()
    finally:
        released.set()
        callback.cancel()

    assert loop_ran == [True]
    assert report.gpu_energy_usage == 2.0
