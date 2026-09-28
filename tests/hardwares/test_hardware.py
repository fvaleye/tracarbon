import platform
import shutil
from collections import namedtuple

import psutil

from tracarbon import HardwareInfo
from tracarbon.hardwares.gpu import NvidiaGPU


def test_get_platform_should_return_the_platform():
    platform_expected = platform.system()

    platform_returned = HardwareInfo.get_platform()

    assert platform_returned == platform_expected


CPUTimes = namedtuple("CPUTimes", "user nice system idle")
LinuxCPUTimes = namedtuple("LinuxCPUTimes", "user nice system idle iowait irq softirq steal guest guest_nice")


def test_get_cpu_usage_measures_the_load_since_the_cpu_times_given(mocker):
    now = CPUTimes(user=130.0, nice=0.0, system=20.0, idle=150.0)
    mocker.patch.object(psutil, "cpu_times", return_value=now)

    cpu_usage, cpu_times = HardwareInfo.get_cpu_usage(since=CPUTimes(user=100.0, nice=0.0, system=10.0, idle=90.0))

    assert cpu_usage == 40.0
    assert cpu_times == now


def test_get_cpu_usage_measures_the_load_since_boot_without_earlier_cpu_times(mocker):
    mocker.patch.object(psutil, "cpu_times", return_value=CPUTimes(user=20.0, nice=0.0, system=10.0, idle=70.0))

    cpu_usage, _ = HardwareInfo.get_cpu_usage()

    assert cpu_usage == 30.0


def test_get_cpu_usage_counts_guest_and_iowait_time_the_way_psutil_does(mocker):
    since = LinuxCPUTimes(*[0.0] * 10)
    mocker.patch.object(
        psutil,
        "cpu_times",
        return_value=since._replace(user=50.0, system=10.0, idle=20.0, iowait=20.0, guest=10.0),
    )

    cpu_usage, _ = HardwareInfo.get_cpu_usage(since=since)

    assert cpu_usage == 60.0


def test_get_cpu_usage_ignores_a_counter_that_went_backwards(mocker):
    mocker.patch.object(psutil, "cpu_times", return_value=CPUTimes(user=150.0, nice=0.0, system=0.0, idle=80.0))

    cpu_usage, _ = HardwareInfo.get_cpu_usage(since=CPUTimes(user=100.0, nice=0.0, system=0.0, idle=90.0))

    assert cpu_usage == 100.0


def test_get_cpu_usage_reads_no_load_when_no_cpu_time_was_counted_since(mocker):
    now = CPUTimes(user=100.0, nice=0.0, system=0.0, idle=100.0)
    mocker.patch.object(psutil, "cpu_times", return_value=now)

    cpu_usage, _ = HardwareInfo.get_cpu_usage(since=now)

    assert cpu_usage == 0.0


def test_get_memory_usage(mocker):
    memory_usage_expected = 30.0
    Memory = namedtuple("Memory", "percent")
    return_value = Memory(percent=memory_usage_expected)
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
    gpu_power_usage_returned = b"226 W"
    gpu_usage_expected = 226
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")

    gpu_usage = HardwareInfo.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_gpu_power_usage_with_non_zero_return_code(mocker):
    from tracarbon.exceptions import HardwareNoGPUDetectedException
    from tracarbon.hardwares.gpu import GPUInfo

    mocker.patch.object(
        NvidiaGPU,
        "get_gpu_power_usage",
        side_effect=HardwareNoGPUDetectedException("No Nvidia GPU detected."),
    )
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")
    mocker.patch("tracarbon.hardwares.gpu.shutil.which", return_value=None)

    gpu_usage = GPUInfo.get_gpu_power_usage()
    assert gpu_usage == 0.0


def test_get_gpu_power_usage_with_no_gpu(mocker):
    mocker.patch.object(shutil, "which", return_value=None)

    gpu_usage = HardwareInfo.get_gpu_power_usage()
    assert gpu_usage == 0.0
