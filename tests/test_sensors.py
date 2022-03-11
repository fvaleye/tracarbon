import pytest

from tracarbon import EnergyConsumption


@pytest.mark.darwin
def test_get_platform_should_return_the_platform_energy_consumption_mac():
    energy_consumption = EnergyConsumption.from_platform()

    assert (
        energy_consumption.shell_command
        == """/usr/sbin/ioreg -rw0 -c AppleSmartBattery | grep BatteryData | grep -o '"AdapterPower"=[0-9]*' | cut -c 16- | xargs -I %  lldb --batch -o "print/f %" | grep -o '$0 = [0-9.]*' | cut -c 6-"""
    )
    assert energy_consumption.init is False


@pytest.mark.linux
def test_get_platform_should_return_the_platform_energy_consumption_linux():
    with pytest.raises(ValueError) as exception:
        EnergyConsumption.from_platform()
    assert exception.value.args[0] == "This platform Linux is not yet implemented."


@pytest.mark.windows
def test_get_platform_should_return_the_platform_energy_consumption_windows():
    with pytest.raises(ValueError) as exception:
        EnergyConsumption.from_platform()
    assert exception.value.args[0] == "This platform Windows is not yet implemented."
