import time
from typing import List, Optional

import typer
from loguru import logger

from tracarbon import CarbonEmission, Country, EnergyConsumption
from tracarbon.builder import TracarbonBuilder
from tracarbon.exporters import Exporter, Metric, Tag
from tracarbon.hardwares import HardwareInfo

app = typer.Typer()


@app.command(help="List the exporters")
def list_exporters(displayed: bool = True) -> List[str]:
    """
    List all the exporters available.
    """
    exporters = [cls.get_name() for cls in Exporter.__subclasses__()]
    if displayed:
        logger.info(f"Available Exporters: {exporters}")
    return exporters


def get_exporter(
    exporter_name: str,
    metrics: List[Metric],
    tracarbon_builder: TracarbonBuilder = TracarbonBuilder(),
) -> Exporter:
    """
    Get the exporter based on the name with its metrics.

    :param exporter_name: the name of the exporter
    :param metrics: the list of the associated metrics
    :param tracarbon_builder: the configuration of Tracarbon
    :return: the configured exporter
    """
    exporters = list_exporters(displayed=False)
    if exporter_name not in exporters:
        raise ValueError(f"This exporter is not available in the list: {exporters}")

    try:
        selected_exporter = next(
            cls for cls in Exporter.__subclasses__() if cls.get_name() == exporter_name
        )
    except Exception as exception:
        logger.exception("This exporter initiation failed.")
        raise exception
    return selected_exporter(metrics=metrics, metric_prefix_name=tracarbon_builder.configuration.metric_prefix_name)  # type: ignore


def run_metrics(
    exporter_name: str,
    country_code_alpha_iso_2: Optional[str] = None,
    running: bool = True,
) -> None:
    """
    Run the metrics with the selected exporter

    :param country_code_alpha_iso_2: the alpha iso2 country name where it's running
    :param running: keep running the metrics
    :param exporter_name: the exporter name to run
    :return:
    """
    tracarbon_builder = TracarbonBuilder()
    location = Country.get_location(
        co2signal_api_key=tracarbon_builder.configuration.co2signal_api_key,
        country_code_alpha_iso_2=country_code_alpha_iso_2,
    )
    platform = HardwareInfo.get_platform()
    metrics = list()
    metrics.append(
        Metric(
            name="energy_consumption",
            value=EnergyConsumption.from_platform().run,
            tags=[
                Tag(key="platform", value=platform),
                Tag(key="location", value=location.name),
            ],
        )
    )
    metrics.append(
        Metric(
            name="co2_emission",
            value=CarbonEmission(
                co2signal_api_key=tracarbon_builder.configuration.co2signal_api_key,
                location=location,
            ).run,
            tags=[
                Tag(key="platform", value=platform),
                Tag(key="location", value=location.name),
                Tag(key="source", value=location.co2g_kwh_source.value),
            ],
        )
    )
    metrics.append(
        Metric(
            name="hardware_memory_usage",
            value=HardwareInfo().get_memory_usage,
            tags=[
                Tag(key="platform", value=platform),
                Tag(key="location", value=location.name),
            ],
        )
    )
    metrics.append(
        Metric(
            name="hardware_cpu_usage",
            value=HardwareInfo().get_cpu_usage,
            tags=[
                Tag(key="platform", value=platform),
                Tag(key="location", value=location.name),
            ],
        )
    )
    try:
        exporter = get_exporter(
            exporter_name=exporter_name,
            metrics=metrics,
            tracarbon_builder=tracarbon_builder,
        )
        tracarbon = tracarbon_builder.build(
            location=location,
            exporter=exporter,
        )
        from loguru import logger

        logger.info("Tracarbon CLI started.")
        with tracarbon:
            while running:
                time.sleep(tracarbon_builder.configuration.interval_in_seconds)
    except KeyboardInterrupt:
        logger.info("Tracarbon CLI exited.")


@app.command()
def run(
    exporter_name: str = "Stdout", country_code_alpha_iso_2: Optional[str] = None
) -> None:
    """
    Run Tracarbon.
    """
    run_metrics(
        exporter_name=exporter_name, country_code_alpha_iso_2=country_code_alpha_iso_2
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
