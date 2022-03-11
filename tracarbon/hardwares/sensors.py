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
        Run the sensor and get the current wattage.

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

        :return: EnergyConsumption
        """
        # Cloud Providers
        if CloudProviders.is_running_on_cloud_provider():
            cloud_provider = CloudProviders.auto_detect()
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


class AWSEC2EnergyConsumption(EnergyConsumption):
    """
    The AWS EC2 Energy Consumption.
    """

    idle: float
    at_10: float
    at_50: float
    at_100: float

    def __init__(self, instance_type: str, **data: Any):
        with importlib.resources.path(
            "tracarbon.hardwares.data", "aws-instances.csv"
        ) as resource:
            try:
                with open(str(resource)) as csvfile:
                    reader = csv.reader(csvfile)

                    for row in reader:
                        if row[0] == instance_type:
                            super().__init__(
                                idle=float(row[27].replace(",", ".")),
                                at_10=float(row[28].replace(",", ".")),
                                at_50=float(row[29].replace(",", ".")),
                                at_100=float(row[30].replace(",", ".")),
                                **data,
                            )
                            return
                raise AWSSensorException(
                    f"The AWS instance type is missing: {instance_type}."
                )
            except Exception as exception:
                logger.exception("Error in the AWSSensor")
                raise AWSSensorException(exception)

    async def run(self) -> float:
        """
        Run the sensor and get the current wattage.

        :return: the metric sent by the sensor.
        """
        cpu_usage = await HardwareInfo.get_cpu_usage()
        logger.debug(f"CPU usage: {cpu_usage}")
        if cpu_usage >= 90:
            return self.at_100
        elif cpu_usage >= 50:
            return self.at_50
        elif cpu_usage >= 10:
            return self.at_10
        else:
            return self.idle
