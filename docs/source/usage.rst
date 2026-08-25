*****
Usage
*****

Tracarbon
=========

1. Set the environment variable or directly set the configuration.
2. Choose :class:`.Exporter` with your list of :class:`.Metric`.
3. Launch Tracarbon!

Run the CLI
===========

Run Tracarbon CLI with the default Stdout exporter and the C02 Signal API:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY tracarbon run

Run Tracarbon CLI with the default Stdout exporter without the CO2 Signal API:

>>> tracarbon run

Run Tracarbon CLI with the default Stdout exporter with a specified location:

>>> tracarbon run --country-code-alpha-iso-2 fr

Run Tracarbon CLI with the Datadog exporter:

>>> TRACARBON_CO2SIGNAL_API_KEY=API_KEY DATADOG_API_KEY=DATADOG_API_KEY DATADOG_APP_KEY=DATADOG_APP_KEY tracarbon run --exporter-name Datadog

Run Tracarbon CLI on Linux hardware with Kubernetes and send the metrics to Prometheus:

>>> tracarbon run --exporter-name Prometheus --containers

With the default metric prefix, container metrics are exposed with these Prometheus names:

===============================================  ====================================================================
Metric                                           Labels
===============================================  ====================================================================
tracarbon_energy_consumption_kubernetes_total    pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_energy_consumption_kubernetes_cpu      pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_energy_consumption_kubernetes_memory   pod_name, pod_namespace, container_name, platform, containers, location, units
tracarbon_carbon_emission_kubernetes_total       pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_cpu         pod_name, pod_namespace, container_name, platform, containers, location, source, units
tracarbon_carbon_emission_kubernetes_memory      pod_name, pod_namespace, container_name, platform, containers, location, source, units
===============================================  ====================================================================

Zero values are exported. If Kubernetes returns no pod metrics, the CLI logs
``No Kubernetes container metrics were collected.`` Host metrics are still exported.

Run the code
============
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> tracarbon = TracarbonBuilder(configuration=configuration).build()
>>> tracarbon.start()
>>> # Your code
>>> total_co2g = tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report
>>> print(report.total_co2g)

``total_co2g`` is ``None`` when no host carbon emission metric was collected. The total reflects collected samples.

Run the code with general metrics
=================================
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>> from tracarbon.exporters import StdoutExporter
>>> from tracarbon.general_metrics import CarbonEmissionGenerator, EnergyConsumptionGenerator
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> metric_generators = [EnergyConsumptionGenerator(), CarbonEmissionGenerator()]
>>> exporter = StdoutExporter(metric_generators=metric_generators) # Your exporter
>>> tracarbon = TracarbonBuilder(configuration=configuration).with_exporter(exporter=exporter).build()
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report

Track one workload
==================
Measure what the host consumed while one block of code ran, from sync code or from inside an event loop:

>>> from tracarbon import track
>>>
>>> with track(name="llm.generate") as tracker:
>>>    response = your_model.generate(prompt)
>>>    tracker.usage.tokens = response.output_tokens
>>>
>>> async with track(name="llm.generate") as tracker:  # inside an async server
>>>    response = await your_model.generate(prompt)
>>>    tracker.usage.tokens = response.output_tokens
>>>
>>> usage = tracker.usage
>>> print(usage.joules, usage.joules_per_token, usage.co2g)
>>> span.set_attributes(usage.otel_attributes)

This is host energy observed during the window, not a share attributed to the workload. The sensors measure the
machine, so two blocks measured over the same window each report the whole machine rather than half of it each.

How the block is measured depends on what the hardware exposes, and ``usage.measurement_method`` says which one you
got:

================  ===========================================  =========================================================
Method            Hardware                                     What it means
================  ===========================================  =========================================================
counter           Intel RAPL, no discrete GPU                  The cumulative counters are read before and after. Exact.
sampled           powermetrics on a Mac, cloud instances       Power is sampled while the block runs and integrated.
not_attributable  a Mac without sudo, a Linux host with a GPU  :class:`.WorkloadNotAttributable` is raised.
================  ===========================================  =========================================================

Without ``sudo`` a Mac falls back to the wall adapter reading, which follows the battery charge rather than the
compute. On Linux, RAPL counts the CPU package and its memory but never a discrete GPU. Both refuse rather than
report a number that misses the hardware doing the work. Anything the sensors did not report stays ``None`` rather
than becoming zero. ``make check-sensor`` compares an idle window against a busy one and fails when the two do not
separate.

Run the code with a custom configuration
=========================================
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>> from tracarbon.exporters import StdoutExporter, MetricGenerator, Metric, Tag
>>> from tracarbon.emissions import CarbonEmission
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> metric_generators = [MetricGenerator(metrics=[Metric(name="custom_metric", value=CustomClass().run, tags=[Tag(key="key", value="value")])])]  # Your custom metrics
>>> exporter = StdoutExporter(metric_generators=metric_generators) # Your exporter
>>> tracarbon = TracarbonBuilder(configuration=configuration).with_exporter(exporter=exporter).build()
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report
