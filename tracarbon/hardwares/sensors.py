import asyncio
import csv
import importlib
from abc import ABC
from abc import abstractmethod
from typing import Any

from loguru import logger
from pydantic import BaseModel

from tracarbon.exceptions import AWSSensorException
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares import EnergyUsage
from tracarbon.hardwares.cloud_providers import CloudProviders
from tracarbon.hardwares.hardware import HardwareInfo
from tracarbon.hardwares.rapl import RAPL


class Sensor(ABC, BaseModel):
    """
    The Sensor contract.
    """

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    @abstractmethod
    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage in watt.

        :return: the generated energy usage.
        """
        pass


class EnergyConsumption(Sensor):
    """
    A sensor to calculate the energy consumption.
    """

    init: bool = False

    @staticmethod
    def from_platform(
        platform: str = HardwareInfo.get_platform(),
    ) -> "EnergyConsumption":
        """
        Get the energy consumption from the local platform or cloud provider.

        :return: the Energy Consumption
        """
        # Cloud Providers
        cloud_provider = CloudProviders.auto_detect()
        if cloud_provider:
            return AWSEC2EnergyConsumption(instance_type=cloud_provider.instance_type)

        # Platform
        if platform == "Darwin":
            return MacEnergyConsumption()
        if platform == "Linux":
            return LinuxEnergyConsumption()
        if platform == "Windows":
            return WindowsEnergyConsumption()
        raise TracarbonException(f"This {platform} hardware is not yet implemented.")

    @abstractmethod
    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        :return: the generated energy usage.
        """
        pass


class MacEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of the Mac, working only if it's plugged into plugged-in wall adapter, in watts.
    """

    shell_command: str = """ioreg -rw0 -a -c AppleSmartBattery | plutil -extract '0.BatteryData.AdapterPower' raw -"""

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        :return: the generated energy usage.
        """
        proc = await asyncio.create_subprocess_shell(self.shell_command, stdout=asyncio.subprocess.PIPE)
        result, _ = await proc.communicate()

        return EnergyUsage(host_energy_usage=float(result))


class LinuxEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of a Linux device: https://github.com/fvaleye/tracarbon/issues/1
    """

    rapl: RAPL = RAPL()

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        :return: the generated energy usage.
        """
        if self.rapl.is_rapl_compatible():
            return await self.rapl.get_energy_report()
        raise TracarbonException(f"This Linux hardware is not yet supported.")


class WindowsEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of a Windows device: https://github.com/fvaleye/tracarbon/issues/2
    """

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        :return: the generated energy usage.
        """
        raise TracarbonException("This Windows hardware is not yet supported.")


class AWSEC2EnergyConsumption(EnergyConsumption):
    """
    The AWS EC2 Energy Consumption.
    """

    cpu_idle: float
    cpu_at_10: float
    cpu_at_50: float
    cpu_at_100: float
    memory_idle: float
    memory_at_10: float
    memory_at_50: float
    memory_at_100: float
    has_gpu: bool
    delta_full_machine: float

    def __init__(self, instance_type: str, **data: Any) -> None:
        with importlib.resources.path("tracarbon.hardwares.data", "aws-instances.csv") as resource:
            try:
                with open(str(resource)) as csvfile:
                    reader = csv.reader(csvfile)

                    for row in reader:
                        if row[0] == instance_type:
                            data["cpu_idle"] = float(row[14].replace(",", "."))
                            data["cpu_at_10"] = float(row[15].replace(",", "."))
                            data["cpu_at_50"] = float(row[16].replace(",", "."))
                            data["cpu_at_100"] = float(row[17].replace(",", "."))
                            data["memory_idle"] = float(row[18].replace(",", "."))
                            data["memory_at_10"] = float(row[19].replace(",", "."))
                            data["memory_at_50"] = float(row[20].replace(",", "."))
                            data["memory_at_100"] = float(row[21].replace(",", "."))
                            data["has_gpu"] = float(row[22].replace(",", ".")) > 0
                            data["delta_full_machine"] = float(row[26].replace(",", "."))
                            super().__init__(
                                **data,
                            )
                            return
                raise AWSSensorException(
                    f"The AWS instance type [{instance_type}] is missing from the aws instances file."
                )
            except Exception as exception:
                logger.exception("Error in the AWSSensor")
                raise AWSSensorException(exception) from exception

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        :return: the generated energy usage.
        """
        cpu_usage = HardwareInfo.get_cpu_usage()
        if cpu_usage >= 90:
            cpu_watts = self.cpu_at_100
        elif cpu_usage >= 50:
            cpu_watts = self.cpu_at_50
        elif cpu_usage >= 10:
            cpu_watts = self.cpu_at_10
        else:
            cpu_watts = self.cpu_idle
        logger.debug(f"CPU: {cpu_watts}W")

        memory_usage = HardwareInfo.get_memory_usage()
        if memory_usage >= 90:
            memory_watts = self.memory_at_100
        elif memory_usage >= 50:
            memory_watts = self.memory_at_50
        elif memory_usage >= 10:
            memory_watts = self.memory_at_10
        else:
            memory_watts = self.memory_idle
        logger.debug(f"Memory: {memory_watts}W")

        gpu_watts = 0.0
        if self.has_gpu:
            gpu_watts = HardwareInfo.get_gpu_power_usage()
            logger.debug(f"CPU: {gpu_watts}W")

        total_watts = cpu_watts + memory_watts + gpu_watts + self.delta_full_machine
        logger.debug(f"Total including the delta of the full machine: {total_watts}W")
        return EnergyUsage(
            host_energy_usage=total_watts,
            cpu_energy_usage=cpu_watts,
            memory_energy_usage=memory_watts,
            gpu_energy_usage=gpu_watts,
        )
