import pytest
import requests

from tracarbon import (
    AWSEC2EnergyConsumption,
    AWSSensorException,
    EnergyConsumption,
    TracarbonException,
)
from tracarbon.hardwares import HardwareInfo
from tracarbon.hardwares.cloud_providers import AWS, CloudProviders


@pytest.mark.darwin
def test_get_platform_should_return_the_platform_energy_consumption_mac(not_ec2_mock):
    energy_consumption = EnergyConsumption.from_platform()

    assert (
        energy_consumption.shell_command
        == """/usr/sbin/ioreg -rw0 -c AppleSmartBattery | grep BatteryData | grep -o '"AdapterPower"=[0-9]*' | cut -c 16- | xargs -I %  lldb --batch -o "print/f %" | grep -o '$0 = [0-9.]*' | cut -c 6-"""
    )
    assert energy_consumption.init is False


def test_get_platform_should_raise_exception(not_ec2_mock):
    with pytest.raises(TracarbonException) as exception:
        EnergyConsumption.from_platform(platform="unknown")
    assert exception.value.args[0] == "This platform unknown is not yet implemented."


def test_is_ec2_should_return_false_on_exception(not_ec2_mock):
    assert AWS.is_ec2() is False


@pytest.mark.asyncio
async def test_aws_sensor_should_return_energy_consumption(mocker):
    aws_ec2_sensor = AWSEC2EnergyConsumption(instance_type="c3.8xlarge")
    value_expected = 118.2

    assert aws_ec2_sensor.idle == 71.0
    assert aws_ec2_sensor.at_10 == 118.2
    assert aws_ec2_sensor.at_50 == 191.1
    assert aws_ec2_sensor.at_100 == 251.2

    mocker.patch.object(HardwareInfo, "get_cpu_usage", return_value=10)

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


@pytest.mark.linux
def test_get_platform_should_return_the_platform_energy_consumption_linux(not_ec2_mock):
    with pytest.raises(TracarbonException) as exception:
        EnergyConsumption.from_platform()
    assert exception.value.args[0] == "This platform Linux is not yet implemented."


@pytest.mark.windows
def test_get_platform_should_return_the_platform_energy_consumption_windows(
    not_ec2_mock,
):
    with pytest.raises(TracarbonException) as exception:
        EnergyConsumption.from_platform()
    assert exception.value.args[0] == "This platform Windows is not yet implemented."
