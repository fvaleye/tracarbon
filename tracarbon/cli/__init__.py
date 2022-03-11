import asyncio
from typing import List

import typer
from loguru import logger

from tracarbon import CarbonEmission, Country, EnergyConsumption
from tracarbon.exporters import Exporter, Metric
from tracarbon.hardwares import HardwareInfo

app = typer.Typer()


@app.command(help="List the exporters")
def list_exporters(displayed: bool = True) -> List[str]:
    exporters = [cls.get_name() for cls in Exporter.__subclasses__()]
    if displayed:
        logger.info(f"Available Exporters: {exporters}")
    return exporters


def get_exporter(exporter: str) -> Exporter:
    exporters = list_exporters(displayed=False)
    if exporter not in exporters:
        raise ValueError(f"This exporter is not available in the list: {exporters}")

    try:
        selected_exporter = next(
            cls for cls in Exporter.__subclasses__() if cls.get_name() == exporter
        )
    except Exception as exception:
        logger.exception("This exporter initiation failed.")
        raise exception
    return selected_exporter()  # type: ignore


async def run_metrics(exporter: Exporter) -> None:
    """
    Run the metrics with the selected exporter

    :param exporter: the exporter to run
    :return:
    """
    metrics = list()
    location = await Country.get_location()
    platform = HardwareInfo.get_platform()
    energy_consumption = EnergyConsumption.from_platform()
    metrics.append(
        Metric(
            name="energy_consumption",
            value=energy_consumption.run,
            tags=[f"platform:{platform}", f"location:{location}"],
        )
    )
    metrics.append(
        Metric(
            name="co2_emission",
            value=CarbonEmission(
                location=location, energy_consumption=energy_consumption
            ).run,
            tags=[f"platform:{platform}", f"location:{location}"],
        )
    )
    metrics.append(
        Metric(
            name="hardware_memory_usage",
            value=HardwareInfo().get_memory_usage,
            tags=[f"platform:{platform}", f"location:{location}"],
        )
    )
    metrics.append(
        Metric(
            name="hardware_cpu_usage",
            value=HardwareInfo().get_cpu_usage,
            tags=[f"platform:{platform}", f"location:{location}"],
        )
    )
    await exporter.launch_all(metrics=metrics)


@app.command()
def run(exporter: str) -> None:
    exporter_selected = get_exporter(exporter=exporter)
    asyncio.run(run_metrics(exporter=exporter_selected))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
