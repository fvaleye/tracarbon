import ctypes
import ctypes.util
import platform
import time
from contextlib import suppress
from dataclasses import dataclass

from tracarbon.exceptions import HardwareIOReportException
from tracarbon.hardwares.energy import UsageType

_IOREPORT_LIBRARY = "/usr/lib/libIOReport.dylib"
_UTF8 = 0x08000100
_MILLIJOULES_PER_UNIT = {"mJ": 1.0, "uJ": 1e-3, "nJ": 1e-6, "J": 1000.0}

# Exclude per-core and per-cluster counters to avoid double-counting.
_AGGREGATE_CHANNEL_TYPES = {
    "CPU Energy": UsageType.CPU,
    "GPU Energy": UsageType.GPU,
    "DRAM": UsageType.MEMORY,
    "ANE": UsageType.HOST,
}


@dataclass(frozen=True, slots=True)
class EnergyInterval:
    millijoules: dict[UsageType, float]
    seconds: float


@dataclass(frozen=True, slots=True)
class _Sample:
    reference: int
    taken_at: float


def _channel_usage_type(name: str) -> UsageType | None:
    if name.startswith("DIE_"):
        name = name[4:].partition("_")[2]
    return next((usage for prefix, usage in _AGGREGATE_CHANNEL_TYPES.items() if name.startswith(prefix)), None)


def _load_frameworks() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    core_foundation_path = ctypes.util.find_library("CoreFoundation")
    if core_foundation_path is None:
        raise HardwareIOReportException("CoreFoundation was not found.")
    pointer = ctypes.c_void_p
    try:
        core_foundation = ctypes.CDLL(core_foundation_path)
        ioreport = ctypes.CDLL(_IOREPORT_LIBRARY)
        for library, signatures in (
            (
                core_foundation,
                {
                    "CFStringCreateWithCString": (pointer, [pointer, ctypes.c_char_p, ctypes.c_uint32]),
                    "CFStringGetCStringPtr": (ctypes.c_char_p, [pointer, ctypes.c_uint32]),
                    "CFStringGetCString": (ctypes.c_bool, [pointer, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]),
                    "CFDictionaryGetValue": (pointer, [pointer, pointer]),
                    "CFDictionaryGetCount": (ctypes.c_long, [pointer]),
                    "CFDictionaryCreateMutableCopy": (pointer, [pointer, ctypes.c_long, pointer]),
                    "CFArrayGetCount": (ctypes.c_long, [pointer]),
                    "CFArrayGetValueAtIndex": (pointer, [pointer, ctypes.c_long]),
                    "CFRelease": (None, [pointer]),
                },
            ),
            (
                ioreport,
                {
                    "IOReportCopyChannelsInGroup": (
                        pointer,
                        [pointer, pointer, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64],
                    ),
                    "IOReportCreateSubscription": (
                        pointer,
                        [pointer, pointer, ctypes.POINTER(pointer), ctypes.c_uint64, pointer],
                    ),
                    "IOReportCreateSamples": (pointer, [pointer, pointer, pointer]),
                    "IOReportCreateSamplesDelta": (pointer, [pointer, pointer, pointer]),
                    "IOReportChannelGetGroup": (pointer, [pointer]),
                    "IOReportChannelGetChannelName": (pointer, [pointer]),
                    "IOReportChannelGetUnitLabel": (pointer, [pointer]),
                    "IOReportSimpleGetIntegerValue": (ctypes.c_int64, [pointer, ctypes.c_int32]),
                },
            ),
        ):
            for name, (return_type, argument_types) in signatures.items():
                function = getattr(library, name)
                function.restype = return_type
                function.argtypes = argument_types
        return core_foundation, ioreport
    except (OSError, AttributeError) as exception:
        raise HardwareIOReportException(f"Could not load IOReport: {exception}") from exception


class IOReportReader:
    """Own an IOReport subscription and its samples. Use one reader per caller."""

    _subscription: int | None = None
    _channels: int | None = None
    _channels_key: int | None = None
    _subscribed_channels: int | None = None
    _previous_sample: _Sample | None = None

    def __init__(self) -> None:
        self._core_foundation, self._ioreport = _load_frameworks()
        try:
            self._channels_key = self._core_foundation.CFStringCreateWithCString(None, b"IOReportChannels", _UTF8)
            if not self._channels_key:
                raise HardwareIOReportException("Could not allocate the energy channel key.")
            self._channels = self._copy_energy_channels()
            subscribed_channels = ctypes.c_void_p()
            self._subscription = self._ioreport.IOReportCreateSubscription(
                None, self._channels, ctypes.byref(subscribed_channels), 0, None
            )
            self._subscribed_channels = subscribed_channels.value
            if not self._subscription:
                raise HardwareIOReportException("IOReport refused the subscription to its energy channels.")
        except Exception:
            self.close()
            raise

    @staticmethod
    def is_available() -> bool:
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            return False
        try:
            ctypes.CDLL(_IOREPORT_LIBRARY)
        except OSError:
            return False
        return True

    def _string(self, reference: int | None) -> str:
        if not reference:
            return ""
        value = self._core_foundation.CFStringGetCStringPtr(reference, _UTF8)
        if value:
            return value.decode()
        buffer = ctypes.create_string_buffer(256)
        if self._core_foundation.CFStringGetCString(reference, buffer, len(buffer), _UTF8):
            return buffer.value.decode()
        return ""

    def _usage_type(self, channel: int) -> UsageType | None:
        if self._string(self._ioreport.IOReportChannelGetGroup(channel)) != "Energy Model":
            return None
        return _channel_usage_type(self._string(self._ioreport.IOReportChannelGetChannelName(channel)))

    def _copy_energy_channels(self) -> int:
        core_foundation = self._core_foundation
        group = core_foundation.CFStringCreateWithCString(None, b"Energy Model", _UTF8)
        if not group:
            raise HardwareIOReportException("Could not allocate the energy group name.")
        try:
            published = self._ioreport.IOReportCopyChannelsInGroup(group, None, 0, 0, 0)
        finally:
            core_foundation.CFRelease(group)
        if not published:
            raise HardwareIOReportException("IOReport published no energy channels.")
        try:
            result = core_foundation.CFDictionaryCreateMutableCopy(
                None, core_foundation.CFDictionaryGetCount(published), published
            )
            if not result:
                raise HardwareIOReportException("Could not allocate the energy channel dictionary.")
            return result
        finally:
            core_foundation.CFRelease(published)

    def _read_channels(self, delta: int) -> dict[UsageType, float]:
        channels = self._core_foundation.CFDictionaryGetValue(delta, self._channels_key)
        millijoules: dict[UsageType, float] = {}
        if channels:
            for index in range(self._core_foundation.CFArrayGetCount(channels)):
                channel = self._core_foundation.CFArrayGetValueAtIndex(channels, index)
                usage = self._usage_type(channel)
                factor = _MILLIJOULES_PER_UNIT.get(
                    self._string(self._ioreport.IOReportChannelGetUnitLabel(channel)).strip()
                )
                if usage is None or factor is None:
                    continue
                energy = self._ioreport.IOReportSimpleGetIntegerValue(channel, 0) * factor
                if usage != UsageType.HOST:
                    millijoules[usage] = millijoules.get(usage, 0.0) + energy
                millijoules[UsageType.HOST] = millijoules.get(UsageType.HOST, 0.0) + energy
        return millijoules

    def read_interval(self) -> EnergyInterval | None:
        """Read a counter delta; the first sample starts the interval and returns None."""
        if self._subscription is None:
            raise HardwareIOReportException("The IOReport reader is closed.")
        previous = self._previous_sample
        self._previous_sample = None
        try:
            reference = self._ioreport.IOReportCreateSamples(self._subscription, self._channels, None)
            if not reference:
                raise HardwareIOReportException("IOReport returned no reading of its energy counters.")
            sample = self._previous_sample = _Sample(reference, time.monotonic())
            if previous is None:
                return None
            delta = self._ioreport.IOReportCreateSamplesDelta(previous.reference, sample.reference, None)
            if not delta:
                raise HardwareIOReportException("IOReport reported no energy between the two samples.")
            try:
                return EnergyInterval(self._read_channels(delta), sample.taken_at - previous.taken_at)
            finally:
                self._core_foundation.CFRelease(delta)
        finally:
            if previous is not None:
                self._core_foundation.CFRelease(previous.reference)

    def close(self) -> None:
        if self._previous_sample is not None:
            self._core_foundation.CFRelease(self._previous_sample.reference)
            self._previous_sample = None
        references = (self._subscribed_channels, self._subscription, self._channels, self._channels_key)
        self._subscribed_channels = self._subscription = self._channels = self._channels_key = None
        for reference in references:
            if reference:
                self._core_foundation.CFRelease(reference)

    def __copy__(self) -> "IOReportReader":
        raise TypeError("IOReportReader owns native resources and cannot be copied.")

    def __deepcopy__(self, memo: dict[int, object]) -> "IOReportReader":
        return self.__copy__()

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()
