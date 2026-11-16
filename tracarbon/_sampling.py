from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Generator
from typing import Iterator

from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.processes import Processes
from tracarbon.hardwares.processes import ProcessUsage
from tracarbon.hardwares.sensors import EnergyConsumption

if TYPE_CHECKING:
    from tracarbon.hardwares.containers import Kubernetes
    from tracarbon.hardwares.containers import Pod


@dataclass
class _Samples:
    energy: dict[int, EnergyUsage] = field(default_factory=dict)
    processes: dict[int, list[ProcessUsage]] = field(default_factory=dict)
    pods: dict[int, list["Pod"]] = field(default_factory=dict)


_samples: ContextVar[_Samples | None] = ContextVar("tracarbon_collection_samples", default=None)


@contextmanager
def collection_samples() -> Generator[None, None, None]:
    token = _samples.set(_Samples())
    try:
        yield
    finally:
        _samples.reset(token)


async def sample_energy(sensor: EnergyConsumption) -> EnergyUsage:
    samples = _samples.get()
    if samples is None:
        return await sensor.get_energy_usage()
    key = id(sensor)
    if key not in samples.energy:
        samples.energy[key] = await sensor.get_energy_usage()
    # Consumers may convert units or mutate the interval energies.
    return samples.energy[key].model_copy(deep=True)


def sample_processes(processes: Processes) -> list[ProcessUsage]:
    samples = _samples.get()
    if samples is None:
        return processes.get_processes_usage()
    key = id(processes)
    if key not in samples.processes:
        samples.processes[key] = processes.get_processes_usage()
    return list(samples.processes[key])


def sample_pods(kubernetes: "Kubernetes") -> Iterator["Pod"]:
    samples = _samples.get()
    if samples is None:
        yield from kubernetes.get_pods_usage()
        return
    key = id(kubernetes)
    if key in samples.pods:
        yield from samples.pods[key]
        return
    pods = []
    for pod in kubernetes.get_pods_usage():
        pods.append(pod)
        yield pod
    samples.pods[key] = pods
