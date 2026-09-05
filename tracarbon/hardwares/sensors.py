import asyncio
import csv
import importlib.resources
import struct
from abc import ABC
from abc import abstractmethod
from typing import Any

from loguru import logger
from pydantic import BaseModel
from pydantic import ConfigDict

from tracarbon.exceptions import AWSSensorException
from tracarbon.exceptions import AzureSensorException
from tracarbon.exceptions import GCPSensorException
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.amd_rapl import AMDRAPL
from tracarbon.hardwares.cloud_providers import AWS
from tracarbon.hardwares.cloud_providers import GCP
from tracarbon.hardwares.cloud_providers import Azure
from tracarbon.hardwares.cloud_providers import CloudProviders
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.gpu import AppleSiliconPowerMetrics
from tracarbon.hardwares.gpu import GPUInfo
from tracarbon.hardwares.hardware import HardwareInfo
from tracarbon.hardwares.ioreport import IOReportEnergy
from tracarbon.hardwares.rapl import RAPL

_MAX_PLAUSIBLE_MAC_POWER_IN_WATTS = 1_000

__all__ = [
    "Sensor",
    "EnergyConsumption",
    "MacEnergyConsumption",
    "LinuxEnergyConsumption",
    "WindowsEnergyConsumption",
    "AWSEC2EnergyConsumption",
    "CloudEnergyConsumption",
    "GCPEnergyConsumption",
    "AzureEnergyConsumption",
    "RAPL",
    "AMDRAPL",
    "EnergyUsage",
    "HardwareInfo",
    "GPUInfo",
    "AppleSiliconPowerMetrics",
]


class Sensor(ABC, BaseModel):
    """
    The Sensor contract.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
            if isinstance(cloud_provider, AWS):
                return AWSEC2EnergyConsumption(instance_type=cloud_provider.instance_type)
            if isinstance(cloud_provider, GCP):
                return GCPEnergyConsumption(instance_type=cloud_provider.instance_type)
            if isinstance(cloud_provider, Azure):
                return AzureEnergyConsumption(instance_type=cloud_provider.instance_type)

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
    Energy Consumption of a Mac in watts.

    Reads the IOReport energy counters on Apple Silicon, which give the energy of an interval
    rather than a power reading held over it, need no elevated privileges and cover CPU, GPU,
    memory and ANE.

    Falls back to powermetrics, which measures the same components but has to be run as root, and
    then to the system power ioreg reports. That last one is the power of the whole machine rather
    than of the chip, and the battery only refreshes it every few tens of seconds, so it does not
    follow what the machine computes and is a last resort.
    """

    shell_command: str = """ioreg -rw0 -a -c AppleSmartBattery | plutil -extract '0.BatteryData.SystemPower' raw -"""
    adapter_shell_command: str = (
        """ioreg -rw0 -a -c AppleSmartBattery | plutil -extract '0.BatteryData.AdapterPower' raw -"""
    )
    _active_sensor: str = ""
    _ioreport: IOReportEnergy | None = None

    @staticmethod
    def _ioreg_power_in_watts(result: bytes) -> float | None:
        try:
            reported_power = result.decode().strip()
            if any(marker in reported_power for marker in (".", "e", "E")):
                watts = float(reported_power)
            else:
                # Integers are either milliwatts or the raw bits of a float in watts.
                raw_power = int(reported_power)
                if raw_power <= _MAX_PLAUSIBLE_MAC_POWER_IN_WATTS * 1000:
                    watts = raw_power / 1000
                else:
                    watts = struct.unpack("!f", struct.pack("!I", raw_power))[0]
        except (UnicodeDecodeError, ValueError, OverflowError, struct.error):
            return None
        return watts if 0 <= watts <= _MAX_PLAUSIBLE_MAC_POWER_IN_WATTS else None

    async def _read_energy_counters(self) -> EnergyUsage | None:
        """
        Read the energy Apple Silicon counted since the previous measurement.

        :return: the energy usage, or None on hardware that counts no energy
        """
        if self._ioreport is None:
            if not IOReportEnergy.is_available():
                return None
            try:
                self._ioreport = IOReportEnergy()
            except Exception as exception:
                logger.debug(f"The energy counters could not be subscribed to: {exception}")
                self._ioreport = None
                return None
        try:
            energy_usage = await self._ioreport.get_energy_report()
        except Exception as exception:
            # Reading them goes through a private framework, so the fallbacks below are what
            # anything unexpected coming back out of it should reach.
            logger.debug(f"The energy counters could not be read: {exception}")
            return None
        if self._active_sensor != "IOReport":
            logger.info("Using the IOReport energy counters for energy measurement (CPU + GPU + memory + ANE)")
            self._active_sensor = "IOReport"
        return energy_usage

    @staticmethod
    async def _read_power(shell_command: str) -> float | None:
        """
        Read a power value in watts from ioreg.

        :param shell_command: the command reading one key of the battery data
        :return: the power in watts, or None if the hardware reports no such key
        """
        proc = await asyncio.create_subprocess_shell(
            shell_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        result, _ = await proc.communicate()
        return MacEnergyConsumption._ioreg_power_in_watts(result)

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        Tries the IOReport energy counters first, then powermetrics for the same components, then
        the system power ioreg reports for the whole machine.

        :return: the generated energy usage.
        """
        energy_usage = await self._read_energy_counters()
        if energy_usage is not None:
            return energy_usage

        try:
            cpu_power, gpu_power, ane_power = AppleSiliconPowerMetrics.get_power_breakdown()
            if cpu_power is not None or gpu_power is not None:
                if self._active_sensor != "powermetrics":
                    logger.info("Using powermetrics for energy measurement (CPU + GPU + ANE)")
                    self._active_sensor = "powermetrics"
                host_power = sum(p for p in (cpu_power, gpu_power, ane_power) if p is not None)
                return EnergyUsage(
                    host_energy_usage=host_power,
                    cpu_energy_usage=cpu_power,
                    gpu_energy_usage=gpu_power,
                )
        except Exception:
            logger.debug("powermetrics not available, falling back to ioreg")

        host_power, sensor = 0.0, "ioreg"
        for candidate, shell_command in (
            ("ioreg SystemPower", self.shell_command),
            ("ioreg AdapterPower", self.adapter_shell_command),
        ):
            reading = await self._read_power(shell_command)
            if reading is not None:
                host_power, sensor = reading, candidate
                break
        else:
            logger.warning("ioreg reports no power on this hardware, the host is reported as drawing none.")
        if self._active_sensor != sensor:
            logger.info(f"Using {sensor} for energy measurement")
            self._active_sensor = sensor

        gpu_power = GPUInfo.get_gpu_power_usage_or_none()

        return EnergyUsage(host_energy_usage=host_power, gpu_energy_usage=gpu_power)


class LinuxEnergyConsumption(EnergyConsumption):
    """
    Energy Consumption of a Linux device.

    Supports both Intel and AMD processors via RAPL:
    - Intel: Uses powercap interface at /sys/class/powercap/intel-rapl
    - AMD (kernel 5.8+): Also uses powercap interface (same path as Intel)
    - AMD (older/alternative): Uses HWMON interface via amd_energy driver

    """

    rapl: RAPL = RAPL()
    amd_rapl: AMDRAPL = AMDRAPL()
    _active_sensor: str = ""

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage.

        Tries sensors in order of preference:
        1. Intel RAPL (powercap) - works for Intel and AMD on kernel 5.8+
        2. AMD RAPL (HWMON) - fallback for AMD with amd_energy driver

        GPU power is also queried if available (NVIDIA or AMD GPU).

        :return: the generated energy usage.
        """
        energy_usage: EnergyUsage
        if self.rapl.is_rapl_compatible():
            if self._active_sensor != "intel_rapl":
                logger.info("Using Intel RAPL (powercap) for energy measurement")
                self._active_sensor = "intel_rapl"
            energy_usage = await self.rapl.get_energy_report()
        elif await self.amd_rapl.is_amd_rapl_compatible():
            if self._active_sensor != "amd_rapl":
                logger.info("Using AMD RAPL (HWMON) for energy measurement")
                self._active_sensor = "amd_rapl"
            energy_usage = await self.amd_rapl.get_energy_report()
        else:
            raise TracarbonException(
                "No supported RAPL interface found. "
                "Intel RAPL requires /sys/class/powercap/intel-rapl. "
                "AMD RAPL requires kernel 5.8+ or amd_energy driver."
            )

        energy_usage.gpu_energy_usage = GPUInfo.get_gpu_power_usage_or_none()
        return energy_usage


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
        resource_file = importlib.resources.files("tracarbon.hardwares.data").joinpath("aws-instances.csv")
        try:
            with resource_file.open("r", encoding="utf-8") as csvfile:
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
            raise AWSSensorException(f"The AWS instance type [{instance_type}] is missing from the aws instances file.")
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


class CloudEnergyConsumption(EnergyConsumption):
    """
    Base class for cloud provider energy consumption.
    Uses linear interpolation between min and max watts based on CPU usage.
    """

    min_watts: float
    max_watts: float
    vcpus: float
    memory_gb: float

    @classmethod
    def _get_csv_filename(cls) -> str:
        """Get the CSV filename for this cloud provider."""
        raise NotImplementedError

    @classmethod
    def _get_provider_name(cls) -> str:
        """Get the provider name for logging."""
        raise NotImplementedError

    @classmethod
    def _get_exception_class(cls) -> type[Exception]:
        """Get the exception class for this cloud provider."""
        raise NotImplementedError

    def __init__(self, instance_type: str, **data: Any) -> None:
        resource_file = importlib.resources.files("tracarbon.hardwares.data").joinpath(self._get_csv_filename())
        exception_class = self._get_exception_class()
        provider_name = self._get_provider_name()
        try:
            with resource_file.open("r", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header
                for row in reader:
                    if row[0] == instance_type:
                        data["vcpus"] = float(row[1])
                        data["memory_gb"] = float(row[2])
                        data["min_watts"] = float(row[3])
                        data["max_watts"] = float(row[4])
                        super().__init__(**data)
                        return
            raise exception_class(
                f"The {provider_name} instance type [{instance_type}] "
                f"is missing from the {provider_name.lower()} instances file."
            )
        except exception_class:
            raise
        except Exception as exception:
            logger.exception(f"Error in the {provider_name}Sensor")
            raise exception_class(exception) from exception

    async def get_energy_usage(self) -> EnergyUsage:
        """
        Run the sensor and generate energy usage using linear interpolation.

        :return: the generated energy usage.
        """
        provider_name = self._get_provider_name()
        cpu_usage = HardwareInfo.get_cpu_usage() / 100.0  # Convert to 0-1 range

        # Linear interpolation: power = min_watts + (max_watts - min_watts) * cpu_usage
        cpu_watts = self.min_watts + (self.max_watts - self.min_watts) * cpu_usage
        logger.debug(f"{provider_name} CPU: {cpu_watts:.2f}W (usage: {cpu_usage * 100:.1f}%)")

        gpu_watts = GPUInfo.get_gpu_power_usage_or_none() or 0.0
        if gpu_watts > 0:
            logger.debug(f"{provider_name} GPU: {gpu_watts:.2f}W")

        total_watts = cpu_watts + gpu_watts
        logger.debug(f"{provider_name} Total: {total_watts:.2f}W")

        return EnergyUsage(
            host_energy_usage=total_watts,
            cpu_energy_usage=cpu_watts,
            gpu_energy_usage=gpu_watts if gpu_watts > 0 else None,
        )


class GCPEnergyConsumption(CloudEnergyConsumption):
    """The GCP Compute Engine Energy Consumption."""

    @classmethod
    def _get_csv_filename(cls) -> str:
        return "gcp-instances.csv"

    @classmethod
    def _get_provider_name(cls) -> str:
        return "GCP"

    @classmethod
    def _get_exception_class(cls) -> type[Exception]:
        return GCPSensorException

    def __init__(self, instance_type: str, **data: Any) -> None:
        super().__init__(instance_type=instance_type, **data)


class AzureEnergyConsumption(CloudEnergyConsumption):
    """The Azure VM Energy Consumption."""

    @classmethod
    def _get_csv_filename(cls) -> str:
        return "azure-instances.csv"

    @classmethod
    def _get_provider_name(cls) -> str:
        return "Azure"

    @classmethod
    def _get_exception_class(cls) -> type[Exception]:
        return AzureSensorException

    def __init__(self, instance_type: str, **data: Any) -> None:
        super().__init__(instance_type=instance_type, **data)
