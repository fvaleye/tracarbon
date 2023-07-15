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

Run Tracarbon CLI on LinuxHardware with Kubernetes send send the metrics to Prometheus:

>>> tracarbon run --exporter-name Prometheus --containers

Run the code
============
>>> from tracarbon import TracarbonBuilder, TracarbonConfiguration
>>>
>>> configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")  # Your configuration
>>> tracarbon = TracarbonBuilder(configuration=configuration).build()
>>> tracarbon.start()
>>> # Your code
>>> tracarbon.stop()
>>>
>>> with tracarbon:
>>>    # Your code
>>>
>>> report = tracarbon.report # Get the report

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
