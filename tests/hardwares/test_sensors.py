import pytest
import requests

from tracarbon import (
    AWSEC2EnergyConsumption,
    EnergyConsumption,
    LinuxEnergyConsumption,
    TracarbonException,
    WindowsEnergyConsumption,
)
from tracarbon.hardwares import HardwareInfo, WindowsEnergyConsumption
from tracarbon.hardwares.cloud_providers import AWS


@pytest.mark.darwin
def test_get_platform_should_return_the_platform_energy_consumption_mac():
    energy_consumption = EnergyConsumption.from_platform()

    assert (
        energy_consumption.shell_command
        == """/usr/sbin/ioreg -rw0 -c AppleSmartBattery | grep BatteryData | grep -o '"AdapterPower"=[0-9]*' | cut -c 16- | xargs -I %  lldb --batch -o "print/f %" | grep -o '$0 = [0-9.]*' | cut -c 6-"""
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
    mocker.patch.object(
        HardwareInfo, "get_gpu_power_usage", return_value=gpu_power_usage
    )
    value_expected = (
        aws_ec2_sensor.cpu_at_50
        + aws_ec2_sensor.memory_at_50
        + aws_ec2_sensor.delta_full_machine
        + gpu_power_usage
    )

    value = await aws_ec2_sensor.run()

    assert value == value_expected


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
    value_expected = (
        aws_ec2_sensor.cpu_at_50
        + aws_ec2_sensor.memory_at_50
        + aws_ec2_sensor.delta_full_machine
    )

    value = await aws_ec2_sensor.run()

    assert value == value_expected


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
    mocker.patch.object(HardwareInfo, "is_rapl_compatible", return_value=False)

    with pytest.raises(TracarbonException) as exception:
        await LinuxEnergyConsumption().run()
    assert exception.value.args[0] == "This Linux hardware is not yet supported."


@pytest.mark.asyncio
async def test_get_platform_should_return_the_platform_energy_consumption_linux(mocker):
    power_usage = 1800000
    mocker.patch.object(HardwareInfo, "is_rapl_compatible", return_value=True)
    mocker.patch.object(HardwareInfo, "get_rapl_power_usage", return_value=power_usage)
    expected = 1.8

    results = await LinuxEnergyConsumption().run()

    assert results == expected


@pytest.mark.asyncio
async def test_get_platform_should_return_the_platform_energy_consumption_windows_error():
    with pytest.raises(TracarbonException) as exception:
        await WindowsEnergyConsumption().run()
        assert exception.value.args[0] == "This Windows hardware is not yet supported."
