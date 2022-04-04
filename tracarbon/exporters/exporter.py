import asyncio
from abc import ABCMeta, abstractmethod
from threading import Event, Lock, Timer
from typing import Awaitable, Callable, List, Optional, Set

from loguru import logger
from pydantic import BaseModel, validator

from tracarbon.conf import tracarbon_configuration as conf


class Exporter(BaseModel, metaclass=ABCMeta):
    """The Exporter interface."""

    metrics: List["Metric"]
    event: Optional[Event] = None
    stopped: bool = False

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def __enter__(self) -> None:
        self.start()

    def __exit__(self, type, value, traceback) -> None:  # type: ignore
        self.stop()

    @abstractmethod
    async def launch(self, metric: "Metric") -> None:
        """
        Launch the exporter.

        :param metric: the metric to send
        :return:
        """
        pass

    def start(self) -> None:
        """
        Start the exporter and a dedicated timer configured with the configured timeout.

        :return:
        """
        self.stopped = False
        if not self.event:
            self.event = Event()

        def _run() -> None:
            asyncio.run(self._launch_all())
            if self.event and not self.stopped and not self.event.is_set():
                timer = Timer(conf.interval_in_seconds, _run, [])
                timer.daemon = True
                timer.start()

        _run()

    def stop(self) -> None:
        """
        Stop the explorer and the associated timer.

        :return:
        """
        self.stopped = True
        if self.event:
            self.event.set()

    async def _launch_all(self) -> None:
        """
        Launch the exporter with all the metrics.

        :return:
        """
        for metric in self.metrics:
            logger.debug(f"Running Metric[{metric}].")
            await self.launch(metric=metric)

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        pass


class Metric(BaseModel):
    """
    Global metric to use for the exporters.
    """

    name: str
    value: Callable[[], Awaitable[float]]
    tags: Optional[List[str]] = None

    @validator("name", always=True)
    def metric_name_prefixed(cls, name: str) -> str:
        return f"{conf.metric_prefix_name}.{name}"
