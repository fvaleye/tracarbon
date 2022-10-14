import asyncio
from abc import ABCMeta, abstractmethod
from threading import Event, Timer
from typing import Awaitable, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel


class Exporter(BaseModel, metaclass=ABCMeta):
    """The Exporter interface."""

    metrics: List["Metric"]
    event: Optional[Event] = None
    stopped: bool = False
    metric_prefix_name: Optional[str] = None

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    @abstractmethod
    async def launch(self, metric: "Metric") -> None:
        """
        Launch the exporter.

        :param metric: the metric to send
        :return:
        """
        pass

    def start(self, interval_in_seconds: int) -> None:
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
                timer = Timer(interval_in_seconds, _run, [])
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


class Tag(BaseModel):
    """
    Tag for a metric.
    """

    key: str
    value: str


class Metric(BaseModel):
    """
    Global metric to use for the exporters.
    """

    name: str
    value: Callable[[], Awaitable[float]]
    tags: List[Tag] = list()

    def format_name(
        self, metric_prefix_name: Optional[str] = None, separator: str = "."
    ) -> str:
        """
        Format the name of the metric with a prefix and separator.

        :param metric_prefix_name: the prefix to insert before the separator and the name.
        :param separator: the separator to use between the prefix and the name.
        """
        if metric_prefix_name:
            return f"{metric_prefix_name}{separator}{self.name}"
        return self.name

    def format_tags(self, separator: str = ":") -> List[str]:
        """
        Format tags with a separator.

        :param separator: the separator to insert between the key and value.
        """
        return [f"{tag.key}{separator}{tag.value}" for tag in self.tags]
