import subprocess

import pytest
import requests
from pytest_mock import MockerFixture

from tracarbon import AMDRAPL
from tracarbon import RAPL
from tracarbon import AWSEC2EnergyConsumption
from tracarbon import EnergyConsumption
from tracarbon import LinuxEnergyConsumption
from tracarbon import TracarbonException
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
async def test_mac_energy_consumption_ioreg_parse_failure_returns_zero(mocker):
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

    assert energy_usage.host_energy_usage == 0.0
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

    mocker.patch.object(HardwareInfo, "get_cpu_usage", return_value=50)
    mocker.patch.object(HardwareInfo, "get_memory_usage", return_value=50)
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

    mocker.patch.object(HardwareInfo, "get_cpu_usage", return_value=50)
    mocker.patch.object(HardwareInfo, "get_memory_usage", return_value=50)
    value_expected = aws_ec2_sensor.cpu_at_50 + aws_ec2_sensor.memory_at_50 + aws_ec2_sensor.delta_full_machine

    energy_usage = await aws_ec2_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage == value_expected


def test_aws_sensor_should_return_error_when_instance_type_is_missing():
    instance_type = "fefe"

    with pytest.raises(TracarbonException):
        AWSEC2EnergyConsumption(instance_type=instance_type)


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

    with pytest.raises(TracarbonException) as exception:
        await LinuxEnergyConsumption().get_energy_usage()
    assert "No supported RAPL interface found" in exception.value.args[0]


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
async def test_get_platform_should_return_the_platform_energy_consumption_windows_error():
    with pytest.raises(TracarbonException) as exception:
        await WindowsEnergyConsumption().get_energy_usage()
        assert exception.value.args[0] == "This Windows hardware is not yet supported."


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
async def test_gcp_sensor_should_return_energy_consumption(mocker):
    gcp_sensor = GCPEnergyConsumption(instance_type="n2-standard-4")

    assert gcp_sensor.vcpus == 4.0
    assert gcp_sensor.memory_gb == 16.0
    assert gcp_sensor.min_watts > 0
    assert gcp_sensor.max_watts > gcp_sensor.min_watts

    mocker.patch.object(HardwareInfo, "get_cpu_usage", return_value=50)
    from tracarbon.hardwares.gpu import GPUInfo

    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)

    energy_usage = await gcp_sensor.get_energy_usage()

    expected_power = gcp_sensor.min_watts + (gcp_sensor.max_watts - gcp_sensor.min_watts) * 0.5
    assert abs(energy_usage.host_energy_usage - expected_power) < 0.01


def test_gcp_sensor_should_return_error_when_instance_type_is_missing():
    instance_type = "unknown-instance-type"

    with pytest.raises(GCPSensorException):
        GCPEnergyConsumption(instance_type=instance_type)


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

    mocker.patch.object(HardwareInfo, "get_cpu_usage", return_value=50)
    from tracarbon.hardwares.gpu import GPUInfo

    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)

    energy_usage = await azure_sensor.get_energy_usage()

    expected_power = azure_sensor.min_watts + (azure_sensor.max_watts - azure_sensor.min_watts) * 0.5
    assert abs(energy_usage.host_energy_usage - expected_power) < 0.01


def test_azure_sensor_should_return_error_when_instance_type_is_missing():
    instance_type = "unknown-instance-type"

    with pytest.raises(AzureSensorException):
        AzureEnergyConsumption(instance_type=instance_type)


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
async def test_mac_energy_consumption_reports_no_power_when_ioreg_reports_neither_key(mocker):
    mocker.patch.object(
        AppleSiliconPowerMetrics,
        "get_power_breakdown",
        side_effect=HardwareNoGPUDetectedException("powermetrics failed to run."),
    )
    mocker.patch.object(GPUInfo, "get_gpu_power_usage_or_none", return_value=None)
    mocker.patch.object(MacEnergyConsumption, "_read_power", side_effect=[None, None])

    mac_sensor = MacEnergyConsumption()
    energy_usage = await mac_sensor.get_energy_usage()

    assert energy_usage.host_energy_usage == 0.0


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
