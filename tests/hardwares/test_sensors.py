import pytest
import requests

from tracarbon import AMDRAPL
from tracarbon import RAPL
from tracarbon import AWSEC2EnergyConsumption
from tracarbon import EnergyConsumption
from tracarbon import LinuxEnergyConsumption
from tracarbon import TracarbonException
from tracarbon.hardwares import EnergyUsage
from tracarbon.hardwares import HardwareInfo
from tracarbon.hardwares import WindowsEnergyConsumption
from tracarbon.hardwares.cloud_providers import AWS


@pytest.mark.darwin
def test_get_platform_should_return_the_platform_energy_consumption_mac():
    energy_consumption = EnergyConsumption.from_platform()

    assert (
        energy_consumption.shell_command
        == """ioreg -rw0 -a -c AppleSmartBattery | plutil -extract '0.BatteryData.AdapterPower' raw -"""
    )
    assert energy_consumption.init is False


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


def test_is_ec2_should_return_true(mocker):
    mocker.patch.object(
        requests,
        "head",
        return_value=None,
    )

    assert AWS.is_ec2() is True


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
async def test_get_platform_should_return_amd_rapl_when_intel_not_available(mocker):
    energy_usage = EnergyUsage(host_energy_usage=2.5)
    mocker.patch.object(RAPL, "is_rapl_compatible", return_value=False)
    mocker.patch.object(AMDRAPL, "is_amd_rapl_compatible", return_value=True)
    mocker.patch.object(
        AMDRAPL,
        "get_energy_report",
        return_value=energy_usage,
    )

    results = await LinuxEnergyConsumption().get_energy_usage()

    assert results == energy_usage


@pytest.mark.asyncio
async def test_get_platform_should_return_the_platform_energy_consumption_windows_error():
    with pytest.raises(TracarbonException) as exception:
        await WindowsEnergyConsumption().get_energy_usage()
        assert exception.value.args[0] == "This Windows hardware is not yet supported."
