import ctypes
import ctypes.util
import platform
import plistlib
import time
from contextlib import suppress
from dataclasses import dataclass

from tracarbon.exceptions import HardwareIOReportException
from tracarbon.hardwares.energy import UsageType
from tracarbon.hardwares.gpu import _run_probe

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

# macOS 27 stalls the Energy Model CPU, DRAM and ANE counters while AppleCLPC keeps counting. AppleCLPC does not
# publish its channels, so they are described by report ID (index << 32 | key), with per-driver keys from macmon
# (https://github.com/vladkens/macmon, src/clpc.rs at 6ebbd71c, Copyright (c) 2024 vladkens, MIT License).
_CLPC_CHANNEL_INDICES = {"CPU Energy": 16, "GPU Energy": 25, "ANE": 24, "DRAM": 26}
_CLPC_CHANNEL_KEYS = {
    "com.apple.driver.AppleT6000CLPCv3": (0x47479059, 0x4519BF1E, 0x9AAA17F8, 0xD6CA0CFB),
    "com.apple.driver.AppleT6002CLPC": (0xB501816B, 0x9E2C3E8B, 0x14D5A574, 0x76704B08),
    "com.apple.driver.AppleT6020CLPC": (0xE301CD75, 0x8F34CC7A, 0x7415FB0F, 0x26244BB6),
    "com.apple.driver.AppleT6022CLPC": (0x76F5FD21, 0x90624499, 0x3C097307, 0xE8F2DDF9),
    "com.apple.driver.AppleT6030CLPC": (0xBE03A01A, 0x472D6C9C, 0xB8990C38, 0x23809C0F),
    "com.apple.driver.AppleT6031CLPC": (0xD81E0084, 0x1085F98B, 0x313A3BE1, 0x65FF699D),
    "com.apple.driver.AppleT6032CLPC": (0xF4A21308, 0x85E80513, 0x63DC8E25, 0x63DCAAE5),
    "com.apple.driver.AppleT6041CLPC": (0x263CF1F0, 0x22E4CF59, 0x7849FB5C, 0xFE932624),
    "com.apple.driver.AppleT6050CLPC": (0xD3AB60BB, 0x27CD4CE5, 0x8C0F1C59, 0xF3C81737),
    "com.apple.driver.AppleT6050dCLPC": (0x18B3010E, 0xEDECA11A, 0x188BD883, 0xA33196F9),
    "com.apple.driver.AppleT8103CLPCv3": (0x2CDD31F2, 0x21BECF42, 0x0667FB81, 0xC0C20839),
    "com.apple.driver.AppleT8112CLPC": (0xB5435137, 0x638D9D52, 0xEA089C36, 0x8B6E0FAA),
    "com.apple.driver.AppleT8122CLPC": (0x54B51C99, 0xCE2DD9DC, 0x960AFE2F, 0x0B9641D3),
    "com.apple.driver.AppleT8132CLPC": (0x4A854D94, 0x3B3E3B79, 0x1FF4A9EC, 0x9A44D225),
    "com.apple.driver.AppleT8140CLPC": (0x9BF54436, 0xEF70589C, 0x569D941B, 0x035F5005),
    "com.apple.driver.AppleT8142CLPC": (0x43708744, 0x6A010933, 0xBC5EFDF0, 0xE13633AA),
    "com.apple.driver.AppleT8152CLPC": (0x485D4BFC, 0x11784654, 0x9380C6BB, 0xE17C13BF),
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
                    "CFDataCreate": (pointer, [pointer, ctypes.c_char_p, ctypes.c_long]),
                    "CFPropertyListCreateWithData": (pointer, [pointer, pointer, ctypes.c_ulong, pointer, pointer]),
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

    group = "Energy Model"
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
            # IOReport refuses unknown CLPC report IDs, or accepts them and never samples them.
            if self._subscribe(self._copy_clpc_channels(), sample_every_channel=True):
                self.group = "CLPC"
            elif not self._subscribe(self._copy_energy_channels()):
                raise HardwareIOReportException("IOReport refused the subscription to its energy channels.")
        except Exception:
            self.close()
            raise

    def _subscribe(self, channels: int | None, *, sample_every_channel: bool = False) -> bool:
        if not channels:
            return False
        subscribed_channels = ctypes.c_void_p()
        subscription = self._ioreport.IOReportCreateSubscription(
            None, channels, ctypes.byref(subscribed_channels), 0, None
        )
        if subscription and sample_every_channel and not self._samples_every_channel(subscription, channels):
            self._core_foundation.CFRelease(subscription)
            subscription = None
        if not subscription:
            for reference in (subscribed_channels.value, channels):
                if reference:
                    self._core_foundation.CFRelease(reference)
            return False
        self._channels = channels
        self._subscription = subscription
        self._subscribed_channels = subscribed_channels.value
        return True

    def _samples_every_channel(self, subscription: int, channels: int) -> bool:
        sample = self._ioreport.IOReportCreateSamples(subscription, channels, None)
        if not sample:
            return False
        try:
            return self._channel_count(sample) == self._channel_count(channels)
        finally:
            self._core_foundation.CFRelease(sample)

    def _channel_count(self, reference: int) -> int:
        channels = self._core_foundation.CFDictionaryGetValue(reference, self._channels_key)
        return self._core_foundation.CFArrayGetCount(channels) if channels else 0

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
        if self._string(self._ioreport.IOReportChannelGetGroup(channel)) != self.group:
            return None
        return _channel_usage_type(self._string(self._ioreport.IOReportChannelGetChannelName(channel)))

    def _copy_clpc_channels(self) -> int | None:
        if platform.mac_ver()[0].partition(".")[0] != "27":
            return None
        try:
            driver = plistlib.loads(_run_probe(["ioreg", "-a", "-r", "-d", "1", "-c", "AppleCLPC"]).stdout)[0]
            keys = _CLPC_CHANNEL_KEYS[driver["CFBundleIdentifier"]]
            driver_id = driver["IORegistryEntryID"]
        except Exception:
            return None
        description = {
            "IOReportChannels": [
                {
                    "DriverID": driver_id,
                    "DriverName": "AppleCLPC",
                    "IOReportGroupName": "CLPC",
                    "IOReportSubGroupName": "Energy Counters",
                    # IOReportTypes.h: one simple integer value, in nanojoules.
                    "IOReportChannelInfo": {"IOReportChannelUnit": 3 << 56 | 118 << 32},
                    "LegendChannel": [index << 32 | key, 1 | 2 << 16 | 1 << 32, name],
                }
                for (name, index), key in zip(_CLPC_CHANNEL_INDICES.items(), keys, strict=True)
            ]
        }
        data = plistlib.dumps(description, fmt=plistlib.FMT_BINARY)
        reference = self._core_foundation.CFDataCreate(None, data, len(data))
        if not reference:
            return None
        try:
            # Mutable, as IOReport's getters cache derived fields in each channel.
            return self._core_foundation.CFPropertyListCreateWithData(None, reference, 1, None, None)
        finally:
            self._core_foundation.CFRelease(reference)

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
                value = self._ioreport.IOReportSimpleGetIntegerValue(channel, 0)
                # A negative delta is IOReport's invalid value or a counter reset, not energy.
                if value < 0:
                    continue
                energy = value * factor
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
