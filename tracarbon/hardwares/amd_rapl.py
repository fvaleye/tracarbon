import asyncio
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List

import aiofiles
from loguru import logger
from pydantic import BaseModel
from pydantic import Field

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.rapl import FIRST_INTERVAL_SECONDS
from tracarbon.hardwares.rapl import RAPLResult
from tracarbon.hardwares.rapl import watts_between

__all__ = [
    "AMDRAPLResult",
    "AMDRAPL",
]


class AMDRAPLResult(RAPLResult):
    """
    Energy reading from the amd_energy HWMON driver.

    The kernel extends 32-bit counters to 64 bits. Decreases are treated as resets.
    """

    label: str
    max_energy_uj: float = 0.0


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
    amd_energy_path: str | None = None
    rapl_results: Dict[str, AMDRAPLResult] = Field(default_factory=dict)
    energy_files: List[str] = Field(default_factory=list)

    async def _find_amd_energy_hwmon(self) -> str | None:
        """
        Find the HWMON device that corresponds to amd_energy driver.

        :return: Path to the amd_energy HWMON device, or None if not found
        """
        if not os.path.exists(self.hwmon_base_path):  # noqa: ASYNC240
            return None

        for hwmon_dir in os.listdir(self.hwmon_base_path):
            hwmon_path = os.path.join(self.hwmon_base_path, hwmon_dir)
            name_file = os.path.join(hwmon_path, "name")

            if os.path.exists(name_file):  # noqa: ASYNC240
                try:
                    async with aiofiles.open(name_file) as f:
                        name = (await f.read()).strip()
                        if name == "amd_energy":
                            logger.debug(f"Found amd_energy HWMON at {hwmon_path}")
                            return hwmon_path
                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not read {name_file}: {e}")
                    continue

        return None

    async def is_amd_rapl_compatible(self) -> bool:
        """
        Check for a readable AMD energy counter in HWMON.

        :return: True if AMD energy HWMON interface is available
        """
        if not (self.amd_energy_path and os.path.exists(self.amd_energy_path)):  # noqa: ASYNC240
            self.amd_energy_path = await self._find_amd_energy_hwmon()
        return self.amd_energy_path is not None and any(
            os.access(counter, os.R_OK)
            for counter in Path(self.amd_energy_path).glob("energy*_input")  # noqa: ASYNC240
        )

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

                async with aiofiles.open(label_file) as f:
                    label = (await f.read()).strip()

                async with aiofiles.open(input_file) as f:
                    energy_uj = float((await f.read()).strip())
                    monotonic_time = time.monotonic()

                # Create a unique name combining index and label
                name = f"amd-{energy_index}-{label}"

                rapl_results.append(
                    AMDRAPLResult(
                        name=name,
                        label=label,
                        energy_uj=energy_uj,
                        timestamp=datetime.now(),
                        monotonic_time=monotonic_time,
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
        Return package power as host and CPU power.

        Without a previous sample, read twice over a short interval.
        Memory and GPU power are not measured by this sensor.

        :return: a power report with None for unmeasured domains
        """
        rapl_results = await self.get_amd_rapl_power_usage()
        if not self.rapl_results:
            self.rapl_results = {rapl_result.name: rapl_result for rapl_result in rapl_results}
            await asyncio.sleep(FIRST_INTERVAL_SECONDS)
            rapl_results = await self.get_amd_rapl_power_usage()
        total_package_watts: float | None = None

        for rapl_result in rapl_results:
            previous_rapl_result = self.rapl_results.get(rapl_result.name, rapl_result)
            self.rapl_results[rapl_result.name] = rapl_result
            watts = watts_between(previous=previous_rapl_result, current=rapl_result, max_power_watts=0.0)
            if watts is not None and self._classify_domain(rapl_result.label) == "package":
                total_package_watts = (total_package_watts or 0.0) + watts

        energy_usage_report = EnergyUsage(
            host_energy_usage=total_package_watts,
            cpu_energy_usage=total_package_watts,
            memory_energy_usage=None,
            gpu_energy_usage=None,
        )

        logger.debug(f"AMD RAPL energy report: {energy_usage_report}")
        return energy_usage_report
