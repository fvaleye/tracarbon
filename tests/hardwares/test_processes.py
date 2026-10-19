import os
import subprocess
import sys
import time
from unittest.mock import Mock

import psutil
import pytest

from tracarbon.hardwares import Processes


def _cpu_times(user: float, children_user: float = 0.0) -> Mock:
    return Mock(user=user, system=0.0, children_user=children_user, children_system=0.0)


def _process(name: str, cpu_seconds: list[float]) -> Mock:
    process = Mock(**{"name.return_value": name, "is_running.return_value": True, "children.return_value": []})
    process.cpu_times.side_effect = [_cpu_times(seconds) for seconds in cpu_seconds]
    return process


def test_cpu_usage_is_the_share_of_total_cpu_capacity_over_each_process_own_reads(mocker):
    cpu_count = 4
    worker, other = _process("worker", [1.0, 3.0]), _process("other", [1.0, 2.75])
    mocker.patch("tracarbon.hardwares.processes.psutil.Process", side_effect={10: worker, 20: other}.__getitem__)
    mocker.patch("tracarbon.hardwares.processes.psutil.cpu_count", return_value=cpu_count)
    mocker.patch("tracarbon.hardwares.processes.time.monotonic", side_effect=[0.0, 0.5, 2.0, 4.0])
    processes = Processes(pids=[10, 20])

    first_usages, second_usages = processes.get_processes_usage(), processes.get_processes_usage()

    assert [usage.cpu_usage for usage in first_usages] == [0.0, 0.0]
    assert [(usage.pid, usage.name) for usage in second_usages] == [(10, "worker"), (20, "other")]
    assert [usage.cpu_usage for usage in second_usages] == pytest.approx(
        [2.0 / (cpu_count * 2.0), 1.75 / (cpu_count * 3.5)]
    )


def test_descendants_count_while_running_and_after_they_are_reaped(mocker):
    cpu_count = 4
    mocker.patch("tracarbon.hardwares.processes._PSUTIL_COUNTS_REAPED_CHILDREN", True)
    parent, child = _process("parent", []), _process("child", [])
    parent.cpu_times.side_effect = [_cpu_times(1.0), _cpu_times(1.2), _cpu_times(1.4, children_user=3.0)]
    parent.children.side_effect = [[child], [child], []]
    child.cpu_times.side_effect = [_cpu_times(1.0), psutil.NoSuchProcess(20)]
    mocker.patch("tracarbon.hardwares.processes.psutil.Process", return_value=parent)
    mocker.patch("tracarbon.hardwares.processes.psutil.cpu_count", return_value=cpu_count)
    mocker.patch("tracarbon.hardwares.processes.time.monotonic", side_effect=[0.0, 1.0, 2.0])
    processes = Processes(pids=[10])
    processes.get_processes_usage()

    reaped_while_read, reaped = processes.get_processes_usage(), processes.get_processes_usage()

    assert reaped_while_read[0].cpu_usage == 0.0
    assert reaped[0].cpu_usage == pytest.approx((1.4 + 3.0 - 2.0) / cpu_count)


def test_a_child_that_exits_without_moving_its_time_to_the_parent_does_not_hide_later_work(mocker):
    cpu_count = 4
    mocker.patch("tracarbon.hardwares.processes._PSUTIL_COUNTS_REAPED_CHILDREN", False)
    parent, child = _process("parent", [1.0, 1.5]), _process("child", [1.0])
    parent.children.side_effect = [[child], []]
    mocker.patch("tracarbon.hardwares.processes.psutil.Process", return_value=parent)
    mocker.patch("tracarbon.hardwares.processes.psutil.cpu_count", return_value=cpu_count)
    mocker.patch("tracarbon.hardwares.processes.time.monotonic", side_effect=[0.0, 1.0])
    processes = Processes(pids=[10])
    processes.get_processes_usage()

    usage = processes.get_processes_usage()[0]

    assert usage.cpu_usage == pytest.approx((1.5 - 1.0) / cpu_count)


def test_a_pid_given_to_another_process_is_no_longer_followed(mocker):
    worker = _process("worker", [1.0])
    mocker.patch("tracarbon.hardwares.processes.psutil.Process", return_value=worker)
    processes = Processes(pids=[10])
    processes.get_processes_usage()
    worker.is_running.return_value = False

    usages_after_the_pid_is_reused = [processes.get_processes_usage() for _ in range(2)]

    assert usages_after_the_pid_is_reused == [[], []]
    assert worker.is_running.call_count == 2


def test_a_pid_that_cannot_be_read_is_skipped_with_a_warning(mocker, caplog):
    mocker.patch("tracarbon.hardwares.processes.psutil.Process", side_effect=psutil.NoSuchProcess(10))

    processes = Processes(pids=[10])

    assert processes.get_processes_usage() == []
    assert "Process 10 cannot be read" in caplog.text


def test_a_busy_child_counts_for_its_waiting_parent_until_the_parent_exits():
    spawn_busy_child = (
        "import subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'while True: pass']); print(flush=True); child.wait()"
    )
    parent = psutil.Popen([sys.executable, "-c", spawn_busy_child], stdout=subprocess.PIPE)
    try:
        parent.stdout.readline()
        processes = Processes(pids=[parent.pid])
        processes.get_processes_usage()
        time.sleep(0.2)
        usages = processes.get_processes_usage()
    finally:
        for process in [*parent.children(recursive=True), parent]:
            process.kill()
        parent.wait()

    assert usages[0].cpu_usage > 0.1 / psutil.cpu_count()
    assert processes.get_processes_usage() == []


@pytest.mark.darwin
@pytest.mark.linux
def test_a_child_that_starts_and_exits_between_two_reads_counts_for_the_current_process():
    burn_half_a_second = "import time\nend = time.process_time() + 0.5\nwhile time.process_time() < end: pass"
    processes = Processes(pids=[os.getpid()])
    processes.get_processes_usage()
    started = time.monotonic()

    subprocess.run([sys.executable, "-c", burn_half_a_second], check=True)
    usage = processes.get_processes_usage()[0]

    assert usage.cpu_usage * psutil.cpu_count() * (time.monotonic() - started) > 0.4
