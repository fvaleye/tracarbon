import asyncio
import copy
import platform

import pytest

from tracarbon.exceptions import HardwareIOReportException
from tracarbon.hardwares._ioreport import IOReportReader
from tracarbon.hardwares._ioreport import _Sample
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import UsageType
from tracarbon.hardwares.ioreport import IOReportEnergy
from tracarbon.hardwares.sensors import MacEnergyConsumption


@pytest.fixture
def native_reader(mocker):
    reader = object.__new__(IOReportReader)
    reader._core_foundation = mocker.Mock()
    reader._ioreport = mocker.Mock()
    reader._subscription = 1
    reader._channels = 2
    reader._channels_key = 3
    reader._subscribed_channels = 4
    reader._previous_sample = _Sample(10, 100.0)
    reader._ioreport.IOReportCreateSamples.side_effect = [20, 21]
    reader._ioreport.IOReportCreateSamplesDelta.side_effect = [30, 31]
    mocker.patch("tracarbon.hardwares._ioreport.time").monotonic.side_effect = [102.0, 102.25]
    mocker.patch("tracarbon.hardwares.ioreport.IOReportReader", return_value=reader)
    yield reader
    reader.close()


@pytest.mark.parametrize(("system", "architecture"), [("Linux", "x86_64"), ("Darwin", "x86_64")])
def test_ioreport_is_unavailable_on_unsupported_platforms(mocker, system, architecture):
    mocker.patch.object(platform, "system", return_value=system)
    mocker.patch.object(platform, "machine", return_value=architecture)

    assert IOReportEnergy.is_available() is False


def test_the_library_exports_the_energy_counters():
    import tracarbon

    assert tracarbon.IOReportEnergy is IOReportEnergy
    assert "IOReportEnergy" in tracarbon.__all__


@pytest.mark.asyncio
async def test_report_converts_native_units_and_measures_each_interval(mocker, native_reader):
    channels = [
        ("Energy Model", "CPU Energy", "mJ", 1000),
        ("Energy Model", "DIE_0_GPU Energy", "nJ", 500_000_000),
        ("Energy Model", "DIE_0_DRAM0", "uJ", 250_000),
        ("Energy Model", "DIE_1_DRAM0", "uJ", 250_000),
        ("Energy Model", "ANE0", "mJ", 100),
        ("Energy Model", "DIE_1_ANE1", "J", 1),
        ("Energy Model", "GPU", "mJ", 100_000),
        ("Energy Model", "PACC1_CPU", "mJ", 100_000),
        ("Other Group", "CPU Energy", "mJ", 100_000),
        ("Energy Model", "CPU Energy", "%", 100),
    ]
    core_foundation, ioreport = native_reader._core_foundation, native_reader._ioreport
    core_foundation.CFDictionaryGetValue.return_value = channels
    core_foundation.CFArrayGetCount.side_effect = len
    core_foundation.CFArrayGetValueAtIndex.side_effect = lambda values, index: values[index]
    ioreport.IOReportChannelGetGroup.side_effect = lambda channel: channel[0]
    ioreport.IOReportChannelGetChannelName.side_effect = lambda channel: channel[1]
    ioreport.IOReportChannelGetUnitLabel.side_effect = lambda channel: channel[2]
    ioreport.IOReportSimpleGetIntegerValue.side_effect = lambda channel, index: channel[3]
    mocker.patch.object(IOReportReader, "_string", side_effect=lambda value: value)

    with IOReportEnergy() as energy:
        assert await energy.get_energy_report() == EnergyUsage(
            host_energy_usage=1.55, cpu_energy_usage=0.5, gpu_energy_usage=0.25, memory_energy_usage=0.25
        )
        assert await energy.get_energy_report() == EnergyUsage(
            host_energy_usage=12.4, cpu_energy_usage=4.0, gpu_energy_usage=2.0, memory_energy_usage=2.0
        )

    assert core_foundation.CFRelease.call_args_list == [
        mocker.call(reference) for reference in (30, 10, 31, 20, 21, 4, 1, 2, 3)
    ]


@pytest.mark.asyncio
async def test_the_first_report_measures_a_short_interval(mocker, native_reader):
    native_reader._previous_sample = None
    mocker.patch.object(IOReportReader, "_read_channels", return_value={UsageType.HOST: 1000.0})
    sleep = mocker.patch("tracarbon.hardwares.ioreport.asyncio.sleep")

    report = await IOReportEnergy().get_energy_report()

    assert report.host_energy_usage == 4.0
    assert report.cpu_energy_usage is None
    sleep.assert_awaited_once_with(0.1)


@pytest.mark.asyncio
async def test_a_failed_snapshot_discards_the_previous_window(native_reader):
    native_reader._ioreport.IOReportCreateSamples.side_effect = [None]

    with pytest.raises(HardwareIOReportException):
        await IOReportEnergy().get_energy_report()

    assert native_reader._previous_sample is None
    native_reader._core_foundation.CFRelease.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_a_failed_delta_does_not_extend_the_next_interval(mocker, native_reader):
    native_reader._ioreport.IOReportCreateSamplesDelta.side_effect = [None, 31]
    mocker.patch.object(IOReportReader, "_read_channels", return_value={UsageType.HOST: 1000.0})
    energy = IOReportEnergy()

    with pytest.raises(HardwareIOReportException):
        await energy.get_energy_report()

    assert (await energy.get_energy_report()).host_energy_usage == 4.0
    assert native_reader._core_foundation.CFRelease.call_args_list == [
        mocker.call(10),
        mocker.call(31),
        mocker.call(20),
    ]


@pytest.mark.parametrize(("millijoules", "expected_watts"), [({}, 7.0), ({UsageType.HOST: 0.0}, 0.0)])
@pytest.mark.asyncio
async def test_missing_channels_fall_back_but_zero_energy_does_not(mocker, native_reader, millijoules, expected_watts):
    mocker.patch.object(IOReportReader, "_read_channels", return_value=millijoules)
    mocker.patch(
        "tracarbon.hardwares.sensors.AppleSiliconPowerMetrics.get_power_breakdown", return_value=(5.0, 2.0, None)
    )
    sensor = MacEnergyConsumption()
    sensor._ioreport = IOReportEnergy()

    assert (await sensor.get_energy_usage()).host_energy_usage == expected_watts


@pytest.mark.asyncio
async def test_a_zero_length_interval_is_rejected(mocker, native_reader):
    mocker.patch("tracarbon.hardwares._ioreport.time").monotonic.return_value = 100.0
    mocker.patch.object(IOReportReader, "_read_channels", return_value={UsageType.HOST: 1000.0})

    with pytest.raises(HardwareIOReportException):
        await IOReportEnergy().get_energy_report()


@pytest.mark.parametrize("copy_reader", [copy.copy, copy.deepcopy])
def test_native_resource_ownership_cannot_be_copied(native_reader, copy_reader):
    with pytest.raises(TypeError):
        copy_reader(native_reader)


def test_copying_the_adapter_does_not_double_release_native_resources(mocker, native_reader):
    energy = IOReportEnergy()
    copy.copy(energy).close()
    energy.close()

    assert native_reader._core_foundation.CFRelease.call_args_list == [
        mocker.call(reference) for reference in (10, 4, 1, 2, 3)
    ]
    with pytest.raises(HardwareIOReportException):
        native_reader.read_interval()


def test_a_failed_subscription_releases_allocated_resources(mocker):
    core_foundation, ioreport = mocker.Mock(), mocker.Mock()
    core_foundation.CFStringCreateWithCString.side_effect = [3, 5]
    core_foundation.CFDictionaryCreateMutableCopy.return_value = 2
    ioreport.IOReportCopyChannelsInGroup.return_value = 6
    mocker.patch("tracarbon.hardwares._ioreport._load_frameworks", return_value=(core_foundation, ioreport))

    def failed_subscription(unused, channels, subscribed_channels, flags, options):
        subscribed_channels._obj.value = 4
        return None

    ioreport.IOReportCreateSubscription.side_effect = failed_subscription

    with pytest.raises(HardwareIOReportException):
        IOReportReader()

    ioreport.IOReportCopyChannelsInGroup.assert_called_once_with(5, None, 0, 0, 0)
    assert core_foundation.CFRelease.call_args_list == [mocker.call(reference) for reference in (5, 6, 4, 2, 3)]


@pytest.mark.darwin
@pytest.mark.asyncio
async def test_independent_readers_can_measure_repeatedly_on_this_machine():
    if not IOReportEnergy.is_available():
        pytest.skip("IOReport requires Apple Silicon.")
    try:
        energy = IOReportEnergy()
    except HardwareIOReportException as exception:
        pytest.skip(str(exception))

    with energy, IOReportEnergy() as other:
        reports = await asyncio.gather(energy.get_energy_report(), other.get_energy_report())
        energy.close()
        await asyncio.sleep(0.01)
        reports.append(await other.get_energy_report())

    for report in reports:
        component_watts = sum(
            value
            for value in (report.cpu_energy_usage, report.gpu_energy_usage, report.memory_energy_usage)
            if value is not None
        )
        assert report.host_energy_usage > 0
        assert report.host_energy_usage >= component_watts or report.host_energy_usage == pytest.approx(component_watts)
        assert report.unit.value == "watts"
