import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

import aiofiles
from loguru import logger
from pydantic import BaseModel
from pydantic import Field

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import Power

__all__ = [
    "AMDRAPLResult",
    "AMDRAPL",
]


class AMDRAPLResult(BaseModel):
    """
    AMD RAPL result after reading the HWMON energy files.
    """

    name: str
    label: str
    energy_uj: float
    timestamp: datetime


class AMDRAPL(BaseModel):
    """
    AMD RAPL to read energy consumption via HWMON interface.

    The amd_energy driver exposes energy counters at:
    /sys/class/hwmon/hwmon*/energy*_input (in microjoules)
    /sys/class/hwmon/hwmon*/energy*_label (domain label)

    Labels follow the pattern:
    - Esocket0, Esocket1, ... : Package/socket level energy
    - Ecore0, Ecore1, ... : Per-core energy
    """

    hwmon_base_path: str = "/sys/class/hwmon"
    amd_energy_path: Optional[str] = None
    rapl_results: Dict[str, AMDRAPLResult] = Field(default_factory=dict)
    energy_files: List[str] = Field(default_factory=list)

    async def _find_amd_energy_hwmon(self) -> Optional[str]:
        """
        Find the HWMON device that corresponds to amd_energy driver.

        :return: Path to the amd_energy HWMON device, or None if not found
        """
        if not os.path.exists(self.hwmon_base_path):
            return None

        for hwmon_dir in os.listdir(self.hwmon_base_path):
            hwmon_path = os.path.join(self.hwmon_base_path, hwmon_dir)
            name_file = os.path.join(hwmon_path, "name")

            if os.path.exists(name_file):
                try:
                    async with aiofiles.open(name_file, "r") as f:
                        name = (await f.read()).strip()
                        if name == "amd_energy":
                            logger.debug(f"Found amd_energy HWMON at {hwmon_path}")
                            return hwmon_path
                except (IOError, PermissionError) as e:
                    logger.debug(f"Could not read {name_file}: {e}")
                    continue

        return None

    async def is_amd_rapl_compatible(self) -> bool:
        """
        Check if AMD RAPL energy measurement is available via HWMON.

        :return: True if AMD energy HWMON interface is available
        """
        if self.amd_energy_path and os.path.exists(self.amd_energy_path):
            return True

        self.amd_energy_path = await self._find_amd_energy_hwmon()
        return self.amd_energy_path is not None

    def get_energy_files_list(self) -> None:
        """
        Get the list of energy files from the AMD HWMON interface.

        :raises ValueError: If AMD energy interface is not available
        """
        if not self.amd_energy_path:
            raise ValueError("AMD energy HWMON interface not found")

        self.energy_files = []
        energy_regex = re.compile(r"energy(\d+)_input")

        for filename in os.listdir(self.amd_energy_path):
            match = energy_regex.match(filename)
            if match:
                energy_index = match.group(1)
                input_file = os.path.join(self.amd_energy_path, f"energy{energy_index}_input")
                label_file = os.path.join(self.amd_energy_path, f"energy{energy_index}_label")

                if os.path.exists(input_file) and os.path.exists(label_file):
                    self.energy_files.append(energy_index)

        logger.debug(f"Found AMD energy files: {self.energy_files}")

    async def get_amd_rapl_power_usage(self) -> List[AMDRAPLResult]:
        """
        Read the AMD RAPL energy measurements from HWMON files.

        :return: List of AMD RAPL results
        """
        rapl_results = []

        try:
            if not self.energy_files:
                self.get_energy_files_list()

            if self.amd_energy_path is None:
                raise ValueError("AMD energy HWMON interface not found")
            for energy_index in self.energy_files:
                input_file = os.path.join(self.amd_energy_path, f"energy{energy_index}_input")
                label_file = os.path.join(self.amd_energy_path, f"energy{energy_index}_label")

                async with aiofiles.open(label_file, "r") as f:
                    label = (await f.read()).strip()

                async with aiofiles.open(input_file, "r") as f:
                    energy_uj = float((await f.read()).strip())

                # Create a unique name combining index and label
                name = f"amd-{energy_index}-{label}"

                rapl_results.append(
                    AMDRAPLResult(
                        name=name,
                        label=label,
                        energy_uj=energy_uj,
                        timestamp=datetime.now(),
                    )
                )

        except Exception as exception:
            logger.exception("AMD RAPL read encountered an issue")
            raise HardwareRAPLException(exception) from exception

        logger.debug(f"AMD RAPL results: {rapl_results}")
        return rapl_results

    def _classify_domain(self, label: str) -> str:
        """
        Classify the AMD energy domain based on its label.

        :param label: The energy domain label (e.g., "Esocket0", "Ecore0")
        :return: Classification: "package", "core", or "unknown"
        """
        label_lower = label.lower()

        if "socket" in label_lower or "pkg" in label_lower:
            return "package"
        elif "core" in label_lower:
            return "core"
        else:
            return "unknown"

    async def get_energy_report(self) -> EnergyUsage:
        """
        Get the energy report based on AMD RAPL HWMON readings.

        AMD RAPL domains:
        - Esocket*: Package-level power (similar to Intel's package domain)
        - Ecore*: Per-core power

        Note: AMD RAPL does not expose separate RAM domain via HWMON.
        For RAM measurements, the package domain includes integrated memory controller.

        :return: EnergyUsage report from AMD RAPL measurements
        """
        rapl_results = await self.get_amd_rapl_power_usage()

        total_package_watts = 0.0

        for rapl_result in rapl_results:
            previous_rapl_result = self.rapl_results.get(rapl_result.name, rapl_result)

            time_difference_seconds = (rapl_result.timestamp - previous_rapl_result.timestamp).total_seconds()
            if time_difference_seconds <= 0:
                time_difference_seconds = 1.0

            energy_uj = rapl_result.energy_uj

            # Handle wrap-around for 32-bit counters on older AMD CPUs
            # 32-bit counter max is ~4.29 billion microjoules
            max_32bit_uj = 4294967295.0
            if previous_rapl_result.energy_uj > rapl_result.energy_uj:
                logger.debug(
                    f"Wrap-around detected in AMD RAPL {rapl_result.name}. "
                    f"Current: {rapl_result.energy_uj}, Previous: {previous_rapl_result.energy_uj}"
                )
                energy_uj = energy_uj + max_32bit_uj

            energy_delta = energy_uj - previous_rapl_result.energy_uj
            watts = Power.watts_from_microjoules(energy_delta / time_difference_seconds)

            # Store current result for next comparison
            self.rapl_results[rapl_result.name] = rapl_result

            domain = self._classify_domain(rapl_result.label)

            if domain == "package":
                total_package_watts += watts

        energy_usage_report = EnergyUsage(
            host_energy_usage=total_package_watts,
            cpu_energy_usage=total_package_watts if total_package_watts > 0 else None,
            memory_energy_usage=None,
            gpu_energy_usage=None,
        )

        logger.debug(f"AMD RAPL energy report: {energy_usage_report}")
        return energy_usage_report
