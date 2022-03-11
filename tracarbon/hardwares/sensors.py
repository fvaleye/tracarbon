import asyncio
from abc import ABC, abstractmethod

from pydantic import BaseModel

from tracarbon.hardwares.hardware import HardwareInfo


class Sensor(ABC, BaseModel):
    """
    The Sensor contract.
    """

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage.

        :return: the metric sent by the sensor.
        """
        pass


class EnergyConsumption(Sensor):
    """
    A sensor to calculate the energy consumption in watts.
    """

    init: bool = False

    @classmethod
    def from_platform(
        cls,
        platform: str = HardwareInfo.get_platform(),
    ) -> "EnergyConsumption":
        """
        Get the energy consumption from the local platform.

        :return: EnergyConsumption
        """
        if platform == "Darwin":
            return MacEnergyConsumption()
        if platform == "Linux":
            LinuxEnergyConsumption()
        if platform == "Windows":
            WindowsEnergyConsumption()
        raise ValueError(f"This platform {platform} is not yet implemented.")


class MacEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of the Mac, working only if it's plugged into electrical outlet, in watts.
    """

    shell_command: str = """/usr/sbin/ioreg -rw0 -c AppleSmartBattery | grep BatteryData | grep -o '"AdapterPower"=[0-9]*' | cut -c 16- | xargs -I %  lldb --batch -o "print/f %" | grep -o '$0 = [0-9.]*' | cut -c 6-"""

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage.

        :return: the sensor metric.
        """
        proc = await asyncio.create_subprocess_shell(
            self.shell_command, stdout=asyncio.subprocess.PIPE
        )
        result, _ = await proc.communicate()
        return float(result)


class LinuxEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of a Linux device: https://github.com/fvaleye/tracarbon/issues/1
    """

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage.

        :return: the sensor metric.
        """
        raise NotImplementedError("Linux platform is not yet supported.")


class WindowsEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of a Windows device: https://github.com/fvaleye/tracarbon/issues/2
    """

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage.

        :return: the sensor metric.
        """
        raise NotImplementedError("Windows platform is not yet supported.")
