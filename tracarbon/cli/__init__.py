import time
from typing import List
from typing import Optional

import typer
from loguru import logger

from tracarbon.builder import TracarbonBuilder
from tracarbon.conf import KUBERNETES_INSTALLED
from tracarbon.exporters import Exporter
from tracarbon.exporters import MetricGenerator
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import EnergyConsumptionGenerator
from tracarbon.locations import Country

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
    metric_generators: List[MetricGenerator],
    tracarbon_builder: Optional[TracarbonBuilder] = None,
) -> Exporter:
    """
    Get the exporter based on the name with its metrics.

    :param exporter_name: the name of the exporter
    :param metric_generators: the list of the metrics generators
    :param tracarbon_builder: the configuration of Tracarbon
    :return: the configured exporter
    """
    if not tracarbon_builder:
        tracarbon_builder = TracarbonBuilder()
    exporters = list_exporters(displayed=False)
    if exporter_name not in exporters:
        raise ValueError(f"This exporter is not available in the list: {exporters}")

    try:
        selected_exporter = next(cls for cls in Exporter.__subclasses__() if cls.get_name() == exporter_name)
    except Exception as exception:
        logger.exception("This exporter initiation failed.")
        raise exception
    return selected_exporter(
        metric_generators=metric_generators, metric_prefix_name=tracarbon_builder.configuration.metric_prefix_name
    )  # type: ignore


def add_containers_generator(location: Country) -> List[MetricGenerator]:
    """
    Add metric generators for containers if available

    :param: country for the metric generators of containers
    :return: the list of metric generators for containers
    """
    if KUBERNETES_INSTALLED:
        from tracarbon.general_metrics import CarbonEmissionKubernetesGenerator
        from tracarbon.general_metrics import EnergyConsumptionKubernetesGenerator

        return [
            EnergyConsumptionKubernetesGenerator(location=location),
            CarbonEmissionKubernetesGenerator(location=location),
        ]
    else:
        raise ImportError("kubernetes optional dependency is not installed")


def run_metrics(
    exporter_name: str,
    country_code_alpha_iso_2: Optional[str] = None,
    running: bool = True,
    containers: bool = False,
) -> None:
    """
    Run the metrics with the selected exporter

    :param country_code_alpha_iso_2: the alpha iso2 country name where it's running
    :param running: keep running the metrics
    :param exporter_name: the exporter name to run
    :param containers: activate the containers feature
    :return:
    """
    tracarbon_builder = TracarbonBuilder()
    location = Country.get_location(
        co2signal_api_key=tracarbon_builder.configuration.co2signal_api_key,
        co2signal_url=tracarbon_builder.configuration.co2signal_url,
        country_code_alpha_iso_2=country_code_alpha_iso_2,
    )
    metric_generators: List[MetricGenerator] = [
        EnergyConsumptionGenerator(location=location),
        CarbonEmissionGenerator(
            location=location,
        ),
    ]
    if containers:
        metric_generators.extend(add_containers_generator(location=location))

    tracarbon = None
    try:
        exporter = get_exporter(
            exporter_name=exporter_name,
            metric_generators=metric_generators,
            tracarbon_builder=tracarbon_builder,
        )
        tracarbon = tracarbon_builder.with_location(location=location).with_exporter(exporter=exporter).build()
        from loguru import logger

        logger.info("Tracarbon CLI started.")
        with tracarbon:
            while running:
                time.sleep(tracarbon_builder.configuration.interval_in_seconds)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Error in Tracarbon execution: {e}")

    if tracarbon:
        logger.info(f"Tracarbon CLI exited. Tracarbon report: {tracarbon.report}")
    else:
        logger.info("Tracarbon CLI exited with errors during initialization.")


@app.command()
def run(
    exporter_name: str = "Stdout",
    country_code_alpha_iso_2: Optional[str] = None,
    containers: bool = False,
) -> None:
    """
    Run Tracarbon.
    """
    run_metrics(
        exporter_name=exporter_name,
        country_code_alpha_iso_2=country_code_alpha_iso_2,
        containers=containers,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
