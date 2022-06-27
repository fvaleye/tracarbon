import asyncio
import csv
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from loguru import logger
from pydantic import BaseModel

from tracarbon.exceptions import AWSSensorException, TracarbonException
from tracarbon.hardwares.cloud_providers import CloudProviders
from tracarbon.hardwares.hardware import HardwareInfo


class Sensor(ABC, BaseModel):
    """
    The Sensor contract.
    """

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage in watt.

        :return: the metric sent by the sensor.
        """
        pass


class EnergyConsumption(Sensor):
    """
    A sensor to calculate the energy consumption in watts.
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
            LinuxEnergyConsumption()
        if platform == "Windows":
            WindowsEnergyConsumption()
        raise TracarbonException(f"This platform {platform} is not yet implemented.")


class MacEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of the Mac, working only if it's plugged into plugged-in wall adapter, in watts.
    """

    shell_command: str = """/usr/sbin/ioreg -rw0 -c AppleSmartBattery | grep BatteryData | grep -o '"AdapterPower"=[0-9]*' | cut -c 16- | xargs -I %  lldb --batch -o "print/f %" | grep -o '$0 = [0-9.]*' | cut -c 6-"""

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage in watts.

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
        Run the sensor and get the current wattage in watts.

        :return: the sensor metric.
        """
        raise NotImplementedError("Linux platform is not yet supported.")


class WindowsEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of a Windows device: https://github.com/fvaleye/tracarbon/issues/2
    """

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage in watts.

        :return: the sensor metric.
        """
        raise NotImplementedError("Windows platform is not yet supported.")


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
        with importlib.resources.path(
            "tracarbon.hardwares.data", "aws-instances.csv"
        ) as resource:
            try:
                with open(str(resource)) as csvfile:
                    reader = csv.reader(csvfile)

                    for row in reader:
                        if row[0] == instance_type:
                            super().__init__(
                                cpu_idle=float(row[14].replace(",", ".")),
                                cpu_at_10=float(row[15].replace(",", ".")),
                                cpu_at_50=float(row[16].replace(",", ".")),
                                cpu_at_100=float(row[17].replace(",", ".")),
                                memory_idle=float(row[18].replace(",", ".")),
                                memory_at_10=float(row[19].replace(",", ".")),
                                memory_at_50=float(row[20].replace(",", ".")),
                                memory_at_100=float(row[21].replace(",", ".")),
                                has_gpu=float(row[22].replace(",", ".")) > 0,
                                delta_full_machine=float(row[26].replace(",", ".")),
                                **data,
                            )
                            return
                raise AWSSensorException(
                    f"The AWS instance type [{instance_type}] is missing from the aws instances file."
                )
            except Exception as exception:
                logger.exception("Error in the AWSSensor")
                raise AWSSensorException(exception)

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage in watts.

        :return: the metric sent by the sensor.
        """
        cpu_usage = await HardwareInfo.get_cpu_usage()
        if cpu_usage >= 90:
            watts = self.cpu_at_100
        elif cpu_usage >= 50:
            watts = self.cpu_at_50
        elif cpu_usage >= 10:
            watts = self.cpu_at_10
        else:
            watts = self.cpu_idle
        logger.debug(f"CPU: {watts}W")

        memory_usage = await HardwareInfo.get_memory_usage()
        if memory_usage >= 90:
            watts += self.memory_at_100
        elif memory_usage >= 50:
            watts += self.memory_at_50
        elif memory_usage >= 10:
            watts += self.memory_at_10
        else:
            watts += self.memory_idle
        logger.debug(f"CPU with memory: {watts}W")

        if self.has_gpu:
            gpu_power_usage = HardwareInfo.get_gpu_power_usage()
            watts += gpu_power_usage
            logger.debug(f"CPU with memory and GPU: {watts}W")

        watts += self.delta_full_machine
        logger.debug(f"Total including the delta of the full machine: {watts}W")
        return watts
