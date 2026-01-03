import shutil

import pytest

from tracarbon.exceptions import HardwareNoGPUDetectedException
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.gpu import AMDGPU
from tracarbon.hardwares.gpu import AppleSiliconGPU
from tracarbon.hardwares.gpu import GPUInfo
from tracarbon.hardwares.gpu import NvidiaGPU


def test_get_nvidia_gpu_power_usage(mocker):
    gpu_power_usage_returned = b"226 W"
    gpu_usage_expected = 226
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))

    gpu_usage = NvidiaGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_nvidia_gpu_power_usage_multi_gpu(mocker):
    gpu_power_usage_returned = b"226.50 W\n185.00 W\n200.25 W"
    gpu_usage_expected = 611.75
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))

    gpu_usage = NvidiaGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_nvidia_gpu_power_usage_should_throw_error():
    with pytest.raises(TracarbonException) as exception:
        NvidiaGPU.get_gpu_power_usage()
    assert exception.value.args[0] == "Nvidia GPU with nvidia-smi not found in PATH."


def test_get_nvidia_gpu_power_usage_with_non_zero_return_code(mocker):
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(b"error", 1))

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        NvidiaGPU.get_gpu_power_usage()
    assert "No Nvidia GPU detected" in exception.value.args[0]


def test_get_amd_gpu_power_usage_rocm_smi(mocker):
    rocm_smi_output = b"""
========================= ROCm System Management Interface =========================
GPU[0]          : Average Graphics Package Power (W): 45.0
GPU[1]          : Average Graphics Package Power (W): 52.5
========================= End of ROCm SMI Log =====================================
"""
    gpu_usage_expected = 97.5
    mocker.patch.object(shutil, "which", return_value="/usr/bin/rocm-smi")
    mocker.patch.object(AMDGPU, "launch_shell_command", return_value=(rocm_smi_output, 0))

    gpu_usage = AMDGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_amd_gpu_power_usage_amd_smi(mocker):
    amd_smi_output = b"""
GPU: 0
    POWER_USAGE: 65.0 W

GPU: 1
    POWER_USAGE: 70.0 W
"""
    gpu_usage_expected = 135.0
    mocker.patch.object(shutil, "which", return_value="/usr/bin/amd-smi")
    mocker.patch.object(AMDGPU, "launch_shell_command", return_value=(amd_smi_output, 0))

    gpu_usage = AMDGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_amd_gpu_power_usage_fallback_rocm_to_amd_smi(mocker):
    amd_smi_output = b"""
GPU: 0
    POWER_USAGE: 50.0 W
"""
    gpu_usage_expected = 50.0

    # Mock shutil.which to return None for rocm-smi and path for amd-smi
    def which_side_effect(cmd):
        if cmd == "rocm-smi":
            return None
        elif cmd == "amd-smi":
            return "/usr/bin/amd-smi"
        return None

    mocker.patch("tracarbon.hardwares.gpu.shutil.which", side_effect=which_side_effect)
    mock_result = mocker.Mock()
    mock_result.stdout = amd_smi_output
    mock_result.returncode = 0
    mocker.patch("tracarbon.hardwares.gpu.subprocess.run", return_value=mock_result)

    gpu_usage = AMDGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_amd_gpu_power_usage_with_non_zero_return_code(mocker):
    mocker.patch.object(shutil, "which", return_value="/usr/bin/rocm-smi")
    mocker.patch.object(AMDGPU, "launch_shell_command", return_value=(b"error", 1))

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        AMDGPU.get_gpu_power_usage()
    assert "No AMD GPU detected" in exception.value.args[0]


def test_get_amd_gpu_power_usage_no_power_matches_found(mocker):
    output_without_power = b"Some output without power values"
    mocker.patch.object(shutil, "which", return_value="/usr/bin/rocm-smi")
    mocker.patch.object(AMDGPU, "launch_shell_command", return_value=(output_without_power, 0))

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        AMDGPU.get_gpu_power_usage()
    assert "No AMD GPU detected" in exception.value.args[0]


def test_get_amd_gpu_power_usage_should_throw_error(mocker):
    mocker.patch.object(shutil, "which", return_value=None)

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        AMDGPU.get_gpu_power_usage()
    assert "AMD GPU tools" in exception.value.args[0]


def test_get_apple_silicon_gpu_power_usage_mw(mocker):
    powermetrics_output = b"""
*** GPU Power ***

GPU Power: 450 mW
"""
    gpu_usage_expected = 0.45
    mocker.patch.object(shutil, "which", return_value="/usr/bin/powermetrics")
    mocker.patch.object(AppleSiliconGPU, "launch_shell_command", return_value=(powermetrics_output, 0))

    gpu_usage = AppleSiliconGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_apple_silicon_gpu_power_usage_watts(mocker):
    powermetrics_output = b"""
*** GPU Power ***

GPU Power: 5.5 W
"""
    gpu_usage_expected = 5.5
    mocker.patch.object(shutil, "which", return_value="/usr/bin/powermetrics")
    mocker.patch.object(AppleSiliconGPU, "launch_shell_command", return_value=(powermetrics_output, 0))

    gpu_usage = AppleSiliconGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_apple_silicon_gpu_power_usage_should_throw_error(mocker):
    mocker.patch.object(shutil, "which", return_value=None)

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        AppleSiliconGPU.get_gpu_power_usage()
    assert "powermetrics" in exception.value.args[0]


def test_get_apple_silicon_gpu_power_usage_with_non_zero_return_code(mocker):
    mocker.patch.object(shutil, "which", return_value="/usr/bin/powermetrics")
    mocker.patch.object(AppleSiliconGPU, "launch_shell_command", return_value=(b"error", 1))

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        AppleSiliconGPU.get_gpu_power_usage()
    assert "Apple Silicon GPU power not available" in exception.value.args[0]


def test_get_apple_silicon_gpu_power_usage_no_power_pattern_match(mocker):
    output_without_power = b"Some output without GPU Power pattern"
    mocker.patch.object(shutil, "which", return_value="/usr/bin/powermetrics")
    mocker.patch.object(AppleSiliconGPU, "launch_shell_command", return_value=(output_without_power, 0))

    with pytest.raises(HardwareNoGPUDetectedException) as exception:
        AppleSiliconGPU.get_gpu_power_usage()
    assert "Apple Silicon GPU power not available" in exception.value.args[0]


def test_get_gpu_power_usage_fallback_returns_zero(mocker):
    mocker.patch.object(shutil, "which", return_value=None)

    gpu_usage = GPUInfo.get_gpu_power_usage()

    assert gpu_usage == 0.0


def test_get_gpu_power_usage_nvidia_detected(mocker):
    gpu_power_usage_returned = b"150 W"
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")

    gpu_usage = GPUInfo.get_gpu_power_usage()

    assert gpu_usage == 150.0


def test_get_gpu_power_usage_or_none_returns_none(mocker):
    mocker.patch.object(shutil, "which", return_value=None)

    gpu_usage = GPUInfo.get_gpu_power_usage_or_none()

    assert gpu_usage is None


def test_get_gpu_power_usage_or_none_returns_value(mocker):
    gpu_power_usage_returned = b"100 W"
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")

    gpu_usage = GPUInfo.get_gpu_power_usage_or_none()

    assert gpu_usage == 100.0


def test_get_gpu_power_usage_or_none_returns_none_when_power_is_zero(mocker):
    gpu_power_usage_returned = b"0 W"
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")

    gpu_usage = GPUInfo.get_gpu_power_usage_or_none()

    assert gpu_usage is None


def test_get_gpu_power_usage_amd_detected(mocker):
    rocm_smi_output = b"""
========================= ROCm System Management Interface =========================
GPU[0]          : Average Graphics Package Power (W): 75.0
========================= End of ROCm SMI Log =====================================
"""
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")
    # First try NVIDIA (not found), then AMD (found)
    mocker.patch.object(
        NvidiaGPU,
        "get_gpu_power_usage",
        side_effect=HardwareNoGPUDetectedException("Nvidia GPU not found"),
    )
    mocker.patch.object(shutil, "which", return_value="/usr/bin/rocm-smi")
    mocker.patch.object(AMDGPU, "launch_shell_command", return_value=(rocm_smi_output, 0))

    gpu_usage = GPUInfo.get_gpu_power_usage()

    assert gpu_usage == 75.0


def test_get_gpu_power_usage_apple_silicon_detected(mocker):
    powermetrics_output = b"""
*** GPU Power ***

GPU Power: 3.5 W
"""
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Darwin")
    mocker.patch.object(shutil, "which", return_value="/usr/bin/powermetrics")
    mocker.patch.object(AppleSiliconGPU, "launch_shell_command", return_value=(powermetrics_output, 0))

    gpu_usage = GPUInfo.get_gpu_power_usage()

    assert gpu_usage == 3.5
