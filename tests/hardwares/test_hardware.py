import platform
from collections import namedtuple

import psutil
import pytest

from tracarbon import RAPL, HardwareInfo
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.gpu import NvidiaGPU


def test_get_platform_should_return_the_platform():
    platform_expected = platform.system()

    platform_returned = HardwareInfo.get_platform()

    assert platform_returned == platform_expected


def test_get_cpu_usage(mocker):
    cpu_usage_expected = 10.0
    mocker.patch.object(psutil, "cpu_percent", return_value=10.0)

    cpu_usage = HardwareInfo.get_cpu_usage()

    assert cpu_usage == cpu_usage_expected


def test_get_memory_usage(mocker):
    memory_usage_expected = 30.0
    Memory = namedtuple("Memory", "used")
    return_value = Memory(used=memory_usage_expected)
    mocker.patch.object(psutil, "virtual_memory", return_value=return_value)

    memory_usage = HardwareInfo.get_memory_usage()

    assert memory_usage == memory_usage_expected


def test_get_memory_total(mocker):
    memory_total_expected = 300000.0
    Memory = namedtuple("Memory", "total")
    return_value = Memory(total=memory_total_expected)
    mocker.patch.object(psutil, "virtual_memory", return_value=return_value)

    memory_usage = HardwareInfo.get_memory_total()

    assert memory_usage == memory_total_expected


def test_get_cpu_count(mocker):
    return_value = 2
    mocker.patch.object(psutil, "cpu_count", return_value=return_value)

    cores = HardwareInfo.get_number_of_cores()

    assert cores == return_value


def test_get_gpu_power_usage(mocker):
    gpu_power_usage_returned = "226 W"
    gpu_usage_expected = 226
    mocker.patch.object(
        NvidiaGPU, "launch_shell_command", return_value=[gpu_power_usage_returned, 0]
    )

    gpu_usage = HardwareInfo.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_gpu_power_usage_with_no_0(mocker):
    gpu_power_usage_returned = "0 W"
    mocker.patch.object(
        NvidiaGPU, "launch_shell_command", return_value=[gpu_power_usage_returned, -1]
    )

    with pytest.raises(TracarbonException) as exception:
        HardwareInfo.get_gpu_power_usage()
    assert exception.value.args[0] == "No Nvidia GPU detected."


def test_get_gpu_power_usage_with_no_gpu():
    with pytest.raises(TracarbonException) as exception:
        HardwareInfo.get_gpu_power_usage()
    assert exception.value.args[0] == "No Nvidia GPU detected."
