import asyncio
from abc import ABCMeta, abstractmethod
from typing import Awaitable, Callable, List, Optional, Set

from loguru import logger
from pydantic import BaseModel, validator

from tracarbon.conf import tracarbon_configuration as conf


class Exporter(BaseModel, metaclass=ABCMeta):
    """The Exporter interface."""

    quit: bool = False

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

    async def launch_all(self, metrics: List["Metric"]) -> None:
        while True:
            for metric in metrics:
                logger.debug(f"Running Metric[{metric}].")
                await self.launch(metric=metric)
            if self.quit:
                break
            await asyncio.sleep(conf.interval_in_seconds)

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the exporter.

        :return: the Exporter's name
        """
        pass


class Metric(BaseModel):
    """
    Global metric for the exporters.
    """

    name: str
    value: Callable[[], Awaitable[float]]
    tags: Optional[List[str]] = None

    @validator("name", always=True)
    def metric_name_prefixed(cls, name: str) -> str:
        return f"{conf.metric_prefix_name}.{name}"
