import functools
import platform
import re
import shutil
import subprocess
from abc import ABC
from typing import Optional
from typing import Tuple

from loguru import logger
from pydantic import BaseModel

from tracarbon.exceptions import HardwareNoGPUDetectedException

_RE_POWER_W = re.compile(r"Power\s*\(W\):\s*([\d.]+)", re.IGNORECASE)
_RE_POWER_USAGE_W = re.compile(r"POWER[^:]*:\s*([\d.]+)\s*W", re.IGNORECASE)


@functools.lru_cache(maxsize=8)
def _compile_power_pattern(label: str, unit: str) -> re.Pattern:
    return re.compile(rf"{label}:\s*([\d.]+)\s*{unit}", re.IGNORECASE)


class NvidiaGPU(BaseModel):
    """
    Nvidia GPU information.
    Supports multiple GPUs by summing power consumption across all detected GPUs.
    """

    @classmethod
    def launch_shell_command(cls) -> Tuple[bytes, int]:
        """
        Launch a shell command to query GPU power.

        :return: result of the shell command and returncode
        """
        nvidia_smi_path = shutil.which("nvidia-smi")
        if nvidia_smi_path is None:
            raise HardwareNoGPUDetectedException("Nvidia GPU with nvidia-smi not found in PATH.")

        result = subprocess.run(
            [nvidia_smi_path, "--query-gpu=power.draw", "--format=csv,noheader"],
            capture_output=True,
        )
        return result.stdout, result.returncode

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.
        Supports multiple GPUs by summing power consumption.

        :return: the total gpu power usage in W
        """
        gpu_output, return_code = cls.launch_shell_command()
        if return_code == 0:
            total_power = 0.0
            for line in gpu_output.decode().strip().split("\n"):
                line = line.strip()
                if line:
                    # Parse decimal number
                    power_str = line.split()[0]
                    total_power += float(power_str)
            return total_power
        raise HardwareNoGPUDetectedException("No Nvidia GPU detected.")


class AMDGPU(BaseModel):
    """
    AMD GPU information using rocm-smi or amd-smi.
    Supports multiple GPUs by summing power consumption across all detected GPUs.
    """

    @classmethod
    def launch_shell_command(cls) -> Tuple[bytes, int]:
        """
        Launch a shell command to query AMD GPU power.
        Tries rocm-smi first, then falls back to amd-smi.

        :return: result of the shell command and returncode
        """
        # Try rocm-smi first
        rocm_smi_path = shutil.which("rocm-smi")
        if rocm_smi_path is not None:
            result = subprocess.run(
                [rocm_smi_path, "--showpower"],
                capture_output=True,
            )
            return result.stdout, result.returncode

        # Fall back to amd-smi
        amd_smi_path = shutil.which("amd-smi")
        if amd_smi_path is not None:
            result = subprocess.run(
                [amd_smi_path, "metric", "--power"],
                capture_output=True,
            )
            return result.stdout, result.returncode

        raise HardwareNoGPUDetectedException("AMD GPU tools (rocm-smi or amd-smi) not found in PATH.")

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the AMD GPU power usage in watts.
        Supports multiple GPUs by summing power consumption.

        :return: the total gpu power usage in W
        """
        gpu_output, return_code = cls.launch_shell_command()
        if return_code == 0:
            total_power = 0.0
            output_str = gpu_output.decode()
            power_matches = _RE_POWER_W.findall(output_str)
            power_matches += _RE_POWER_USAGE_W.findall(output_str)
            for power_str in power_matches:
                total_power += float(power_str)
            if total_power > 0:
                return total_power
        raise HardwareNoGPUDetectedException("No AMD GPU detected or unable to read power.")


class AppleSiliconPowerMetrics(BaseModel):
    """
    Apple Silicon power metrics using powermetrics.
    Parses CPU, GPU, and ANE power from powermetrics output.
    Note: powermetrics requires sudo privileges.
    """

    @classmethod
    def _run_powermetrics(cls, samplers: str) -> Tuple[bytes, int]:
        """
        Run powermetrics with the given samplers.
        Tries without sudo first, falls back to sudo -n if needed.

        :param samplers: comma-separated sampler names (e.g. "cpu_power,gpu_power")
        :return: result of the shell command and returncode
        """
        powermetrics_path = shutil.which("powermetrics")
        if powermetrics_path is None:
            raise HardwareNoGPUDetectedException("powermetrics not found in PATH.")

        result = subprocess.run(
            [powermetrics_path, "--samplers", samplers, "-i", "1", "-n", "1"],
            capture_output=True,
            timeout=10,
        )

        if (
            result.returncode != 0
            and result.stderr
            and (b"superuser" in result.stderr.lower() or b"root" in result.stderr.lower())
        ):
            sudo_path = shutil.which("sudo")
            if sudo_path:
                result = subprocess.run(
                    [sudo_path, "-n", powermetrics_path, "--samplers", samplers, "-i", "1", "-n", "1"],
                    capture_output=True,
                    timeout=10,
                )

        return result.stdout, result.returncode

    @classmethod
    def _parse_power_mw(cls, output: str, label: str) -> Optional[float]:
        """
        Parse a power value from powermetrics output.
        Handles both mW and W units, returns watts.

        :param output: the powermetrics output string
        :param label: the label to search for (e.g. "CPU Power", "GPU Power")
        :return: power in watts, or None if not found
        """
        match = _compile_power_pattern(label, "mW").search(output)
        if match:
            return float(match.group(1)) / 1000.0
        match = _compile_power_pattern(label, "W").search(output)
        if match:
            return float(match.group(1))
        return None

    @classmethod
    def launch_shell_command(cls) -> Tuple[bytes, int]:
        """
        Launch powermetrics to query CPU and GPU power.

        :return: result of the shell command and returncode
        """
        return cls._run_powermetrics("cpu_power,gpu_power")

    @classmethod
    def get_power_breakdown(cls) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Get CPU, GPU, and ANE power in watts from powermetrics.

        :return: tuple of (cpu_power, gpu_power, ane_power) in watts, None if unavailable
        """
        output, return_code = cls.launch_shell_command()
        if return_code != 0:
            raise HardwareNoGPUDetectedException("powermetrics failed to run.")

        output_str = output.decode()
        cpu_power = cls._parse_power_mw(output_str, "CPU Power")
        gpu_power = cls._parse_power_mw(output_str, "GPU Power")
        ane_power = cls._parse_power_mw(output_str, "ANE Power")

        return cpu_power, gpu_power, ane_power

    @classmethod
    def get_combined_power(cls) -> Optional[float]:
        """
        Get the combined power (CPU + GPU + ANE) in watts.
        Falls back to summing individual components if Combined Power line is not found.

        :return: combined power in watts, or None if unavailable
        """
        output, return_code = cls.launch_shell_command()
        if return_code != 0:
            return None

        output_str = output.decode()

        combined = cls._parse_power_mw(output_str, r"Combined Power \(CPU \+ GPU \+ ANE\)")
        if combined is not None:
            return combined

        cpu = cls._parse_power_mw(output_str, "CPU Power")
        gpu = cls._parse_power_mw(output_str, "GPU Power")
        ane = cls._parse_power_mw(output_str, "ANE Power")

        parts = [p for p in (cpu, gpu, ane) if p is not None]
        return sum(parts) if parts else None


class AppleSiliconGPU(BaseModel):
    """
    Apple Silicon GPU information using powermetrics.
    Note: powermetrics may require sudo privileges for full access.
    """

    @classmethod
    def launch_shell_command(cls) -> Tuple[bytes, int]:
        """
        Launch powermetrics to query GPU power.
        Delegates to AppleSiliconPowerMetrics.

        :return: result of the shell command and returncode
        """
        return AppleSiliconPowerMetrics._run_powermetrics("gpu_power")

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the Apple Silicon GPU power usage in watts.

        :return: the gpu power usage in W
        """
        gpu_output, return_code = cls.launch_shell_command()
        if return_code == 0:
            output_str = gpu_output.decode()
            gpu_power = AppleSiliconPowerMetrics._parse_power_mw(output_str, "GPU Power")
            if gpu_power is not None:
                return gpu_power
        raise HardwareNoGPUDetectedException("Apple Silicon GPU power not available.")


class GPUInfo(ABC, BaseModel):
    """
    GPU information with auto-detection and graceful fallback.
    Tries all available GPU types and returns 0.0 if none found.
    """

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.
        Auto-detects GPU type and falls back to 0.0 if no GPU is found.

        :return: the gpu power usage in W, or 0.0 if no GPU detected
        """
        platform_name = platform.system()

        # Try platform-specific GPU first
        if platform_name == "Darwin":
            try:
                return AppleSiliconGPU.get_gpu_power_usage()
            except HardwareNoGPUDetectedException:
                logger.debug("Apple Silicon GPU not available")

        # Try NVIDIA (works on Linux, Windows, and Intel Macs)
        try:
            return NvidiaGPU.get_gpu_power_usage()
        except HardwareNoGPUDetectedException:
            logger.debug("NVIDIA GPU not available")

        # Try AMD (Linux)
        if platform_name == "Linux":
            try:
                return AMDGPU.get_gpu_power_usage()
            except HardwareNoGPUDetectedException:
                logger.debug("AMD GPU not available")

        # No GPU found - return 0.0 (graceful fallback)
        logger.debug("No GPU detected, returning 0.0W")
        return 0.0

    @classmethod
    def get_gpu_power_usage_or_none(cls) -> Optional[float]:
        """
        Get the GPU power usage in watts, or None if no GPU is available.

        :return: the gpu power usage in W, or None if no GPU detected
        """
        power = cls.get_gpu_power_usage()
        return power if power > 0.0 else None
