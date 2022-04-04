import time
from typing import List, Optional

import typer
from loguru import logger

from tracarbon import CarbonEmission, Country, EnergyConsumption
from tracarbon.conf import tracarbon_configuration as conf
from tracarbon.exporters import Exporter, Metric
from tracarbon.hardwares import HardwareInfo

app = typer.Typer()


@app.command(help="List the exporters")
def list_exporters(displayed: bool = True) -> List[str]:
    exporters = [cls.get_name() for cls in Exporter.__subclasses__()]
    if displayed:
        logger.info(f"Available Exporters: {exporters}")
    return exporters


def get_exporter(exporter_input: str, metrics: List[Metric]) -> Exporter:
    exporters = list_exporters(displayed=False)
    if exporter_input not in exporters:
        raise ValueError(f"This exporter is not available in the list: {exporters}")

    try:
        selected_exporter = next(
            cls for cls in Exporter.__subclasses__() if cls.get_name() == exporter_input
        )
    except Exception as exception:
        logger.exception("This exporter initiation failed.")
        raise exception
    return selected_exporter(metrics=metrics)  # type: ignore


def run_metrics(
    exporter_input: str,
    country_name_alpha_iso_2: Optional[str] = None,
    running: bool = True,
) -> None:
    """
    Run the metrics with the selected exporter

    :param running: keep running the metrics
    :param exporter_input: the exporter to run
    :return:
    """
    location = Country.get_location(country_name_alpha_iso_2=country_name_alpha_iso_2)
    platform = HardwareInfo.get_platform()
    metrics = list()
    metrics.append(
        Metric(
            name="energy_consumption",
            value=EnergyConsumption.from_platform().run,
            tags=[f"platform:{platform}", f"location:{location.name}"],
        )
    )
    metrics.append(
        Metric(
            name="co2_emission",
            value=CarbonEmission(location=location).run,
            tags=[f"platform:{platform}", f"location:{location}"],
        )
    )
    metrics.append(
        Metric(
            name="hardware_memory_usage",
            value=HardwareInfo().get_memory_usage,
            tags=[f"platform:{platform}", f"location:{location.name}"],
        )
    )
    metrics.append(
        Metric(
            name="hardware_cpu_usage",
            value=HardwareInfo().get_cpu_usage,
            tags=[f"platform:{platform}", f"location:{location.name}"],
        )
    )
    try:
        logger.info("Tracarbon CLI started.")
        with get_exporter(exporter_input=exporter_input, metrics=metrics):
            while running:
                time.sleep(conf.interval_in_seconds)
    except KeyboardInterrupt:
        logger.info("Tracarbon CLI exited.")


@app.command()
def run(exporter_input: str, country_name_alpha_iso_2: Optional[str] = None) -> None:
    run_metrics(
        exporter_input=exporter_input, country_name_alpha_iso_2=country_name_alpha_iso_2
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
