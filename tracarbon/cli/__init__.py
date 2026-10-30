import contextlib
import os
import shutil
import signal
import subprocess
import time
from types import FrameType
from typing import List
from typing import TextIO

import typer
from loguru import logger

from tracarbon.builder import Tracarbon
from tracarbon.builder import TracarbonBuilder
from tracarbon.builder import TracarbonReport
from tracarbon.conf import KUBERNETES_INSTALLED
from tracarbon.conf import TracarbonConfiguration
from tracarbon.conf import logger_configuration
from tracarbon.exporters import Exporter
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import EnergyConsumptionGenerator
from tracarbon.hardwares import UsageType
from tracarbon.locations import Country

app = typer.Typer(pretty_exceptions_show_locals=False)


@app.command(help="List the exporters")
def list_exporters(displayed: bool = True) -> List[str]:
    """
    List all the exporters available.
    """
    exporters = [cls.get_name() for cls in Exporter.__subclasses__()]  # ty: ignore[call-abstract-method]
    if displayed:
        logger.info(f"Available Exporters: {exporters}")
    return exporters


def get_exporter(
    exporter_name: str,
    metric_generators: List[MetricGenerator],
    tracarbon_builder: TracarbonBuilder | None = None,
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
        selected_exporter = next(cls for cls in Exporter.__subclasses__() if cls.get_name() == exporter_name)  # ty: ignore[call-abstract-method]
    except Exception as exception:
        logger.exception("This exporter initiation failed.")
        raise exception
    return selected_exporter(
        metric_generators=metric_generators, metric_prefix_name=tracarbon_builder.configuration.metric_prefix_name
    )


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


def build_tracarbon(
    exporter_name: str,
    configuration: TracarbonConfiguration,
    country_code_alpha_iso_2: str | None = None,
    containers: bool = False,
    pids: List[int] | None = None,
) -> Tracarbon:
    """
    Build Tracarbon reporting the host energy and carbon through the selected exporter.

    :param exporter_name: the exporter name to run
    :param configuration: the configuration of Tracarbon
    :param country_code_alpha_iso_2: the alpha iso2 country name where it's running
    :param containers: activate the containers feature
    :param pids: the processes to attribute CPU energy and carbon emissions to
    :return: the Tracarbon instance, not started
    """
    tracarbon_builder = TracarbonBuilder(configuration=configuration)
    location = Country.get_location(
        co2signal_api_key=configuration.co2signal_api_key,
        co2signal_url=configuration.co2signal_url,
        country_code_alpha_iso_2=country_code_alpha_iso_2,
        emission_factor_type=configuration.emission_factor_type,
    )
    metric_generators: List[MetricGenerator] = [
        EnergyConsumptionGenerator(location=location),
        CarbonEmissionGenerator(
            location=location,
        ),
    ]
    if containers:
        metric_generators.extend(add_containers_generator(location=location))
    if pids:
        tracarbon_builder.with_processes(pids=pids)
    exporter = get_exporter(
        exporter_name=exporter_name,
        metric_generators=metric_generators,
        tracarbon_builder=tracarbon_builder,
    )
    return tracarbon_builder.with_location(location=location).with_exporter(exporter=exporter).build()


def run_metrics(
    exporter_name: str,
    country_code_alpha_iso_2: str | None = None,
    running: bool = True,
    containers: bool = False,
    pids: List[int] | None = None,
) -> None:
    """
    Run the metrics with the selected exporter

    :param country_code_alpha_iso_2: the alpha iso2 country name where it's running
    :param running: keep running the metrics
    :param exporter_name: the exporter name to run
    :param containers: activate the containers feature
    :param pids: the processes to attribute CPU energy and carbon emissions to
    :return:
    """
    tracarbon = None
    collection_failed = False
    try:
        tracarbon = build_tracarbon(
            exporter_name=exporter_name,
            configuration=TracarbonConfiguration(),
            country_code_alpha_iso_2=country_code_alpha_iso_2,
            containers=containers,
            pids=pids,
        )
        logger.info("Tracarbon CLI started.")
        with tracarbon, contextlib.suppress(KeyboardInterrupt):
            while running:
                time.sleep(tracarbon.configuration.interval_in_seconds)
    except KeyboardInterrupt:
        if tracarbon is None:
            raise
    except Exception as e:
        logger.exception(f"Error in Tracarbon execution: {e}")
        collection_failed = True

    if tracarbon:
        if containers and not any("_kubernetes_" in metric_name for metric_name in tracarbon.report.metric_report):
            logger.warning("No Kubernetes container metrics were collected.")
        total_co2g = tracarbon.report.total_co2g
        if total_co2g is None:
            logger.warning("Tracarbon CLI exited. Total CO2 emitted: unavailable")
            gpu_carbon = tracarbon.report.metric_report.get("carbon_emission_gpu")
            if gpu_carbon is not None:
                logger.info(f"GPU CO2 emitted: {gpu_carbon.total:.4f}g")
        else:
            logger.info(f"Tracarbon CLI exited. Total CO2 emitted: {total_co2g:.4f}g")
        logger.info(f"Tracarbon report: {tracarbon.report}")
    else:
        logger.info("Tracarbon CLI exited with errors during initialization.")
    if tracarbon is None or collection_failed:
        raise typer.Exit(code=1)


_PROCESS_ID_OPTION = typer.Option(
    None, min=1, help="Track CPU energy and carbon for this PID and its descendants. Repeat for several."
)


@app.command()
def run(
    exporter_name: str = "Stdout",
    country_code_alpha_iso_2: str | None = None,
    containers: bool = False,
    pid: List[int] | None = _PROCESS_ID_OPTION,
) -> None:
    """
    Run Tracarbon.
    """
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    run_metrics(
        exporter_name=exporter_name,
        country_code_alpha_iso_2=country_code_alpha_iso_2,
        containers=containers,
        pids=pid,
    )


_ENVIRONMENT_BEFORE_DOTENV = dict(os.environ)
_SIGNALS_LEFT_TO_THE_COMMAND = [
    getattr(signal, name) for name in ("SIGINT", "SIGQUIT", "SIGHUP") if hasattr(signal, name)
]


def _keep_measuring(signum: int, frame: FrameType | None) -> None:
    """Unlike SIG_IGN, this handler is not inherited, so the command still gets the signal."""


def _run_command(command: List[str]) -> int:
    """
    Run the command in this terminal, with the environment Tracarbon started with, and forward SIGTERM to it.
    The caller restores the SIGTERM handler.

    :param command: the program and its arguments, passed without a shell
    :return: its exit status, as a shell reports it
    """
    try:
        child = subprocess.Popen(command, env=_ENVIRONMENT_BEFORE_DOTENV)
    except OSError as exception:
        logger.error(f"Command could not run: {exception}")
        return 127 if isinstance(exception, FileNotFoundError) and shutil.which(command[0]) is None else 126
    signal.signal(signal.SIGTERM, lambda signum, _: child.send_signal(signum))
    returncode = child.wait()
    return 128 - returncode if returncode < 0 else returncode


def _summary(report: TracarbonReport) -> str:
    """
    Describe the energy and carbon of each component, or that it is unavailable.

    :param report: the report of the measurement
    :return: the elapsed time, then one line per component
    """
    seconds = (report.end_time - report.start_time).total_seconds() if report.start_time and report.end_time else 0.0
    lines = [f"Tracarbon measured {seconds:.1f} s:"]
    for usage_type in UsageType:
        energy = report.metric_report.get(f"energy_consumption_{usage_type.value}")
        carbon = report.metric_report.get(f"carbon_emission_{usage_type.value}")
        reading = f"{energy.total:.6f} Wh, {carbon.total:.6f} g CO2e" if energy and carbon else "unavailable"
        lines.append(f"  {usage_type.value}: {reading}")
    return "\n".join(lines)


def _finish_measurement(tracarbon: Tracarbon, report_file: TextIO | None) -> bool:
    """
    Take the final reading, then write the report and print the summary, even if that reading fails.

    :param tracarbon: the running Tracarbon
    :param report_file: the new file for the report
    :return: whether the final reading succeeded
    """
    try:
        tracarbon.stop()
        final_reading_succeeded = True
    except Exception:
        logger.exception("Tracarbon could not take its final reading.")
        final_reading_succeeded = False
    if report_file is not None:
        with report_file:
            report_file.write(
                tracarbon.report.model_dump_json(indent=2, exclude={"metric_report": {"__all__": {"metric"}}}) + "\n"
            )
    typer.echo(_summary(tracarbon.report), err=True)
    return final_reading_succeeded


_COMMAND_ARGUMENT = typer.Argument(help="The command to run and its arguments.")
_OUTPUT_OPTION = typer.Option(None, help="Save the report to this new JSON file.")


@app.command("exec", context_settings={"allow_interspersed_args": False})
def exec_command(
    command: List[str] = _COMMAND_ARGUMENT,
    output: str | None = _OUTPUT_OPTION,
    country_code_alpha_iso_2: str | None = None,
) -> None:
    """
    Measure your machine's energy and carbon while a command runs.
    """
    configuration = TracarbonConfiguration(interval_in_seconds=1, log_level="WARNING")
    logger_configuration(level=configuration.log_level)
    tracarbon: Tracarbon | None = None
    try:
        tracarbon = build_tracarbon(
            exporter_name=StdoutExporter.get_name(),
            configuration=configuration,
            country_code_alpha_iso_2=country_code_alpha_iso_2,
        )
        tracarbon.start()
        report_file = open(output, "x") if output else None
    except Exception as exception:
        if tracarbon is not None:
            tracarbon.exporter.stop()
        logger.error(f"Tracarbon could not start, so the command did not run: {exception}")
        raise typer.Exit(code=1) from exception

    previous_handlers = {signum: signal.getsignal(signum) for signum in [*_SIGNALS_LEFT_TO_THE_COMMAND, signal.SIGTERM]}
    for signum in _SIGNALS_LEFT_TO_THE_COMMAND:
        if previous_handlers[signum] is not signal.SIG_IGN:
            signal.signal(signum, _keep_measuring)
    try:
        command_status = _run_command(command)
        final_reading_succeeded = _finish_measurement(tracarbon, report_file)
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    raise typer.Exit(code=command_status or (0 if final_reading_succeeded else 1))


def main() -> None:
    logger_configuration(level=TracarbonConfiguration().log_level)
    app()


if __name__ == "__main__":
    main()
