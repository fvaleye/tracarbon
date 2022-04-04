*****
Usage
*****

Tracarbon
=========

1. Choose :class:`.Exporter`
2. Run it!

Run the CLI
===========

Run the tracarbon cli with Stdout exporter:

>>> tracarbon Stdout

Run the tracarbon cli with Datadog exporter:

>>> DATADOG_API_KEY=DATADOG_API_KEY DATADOG_APP_KEY=DATADOG_APP_KEY tracarbon run Datadog

Run the code
============
>>> from tracarbon import CarbonEmission
>>> from tracarbon.exporters import Metric, StdoutExporter
>>>
>>> metric = Metric(
>>>     name="co2_emission",
>>>     value=CarbonEmission().run,
>>>     tags=[],
>>> )
>>> exporter = StdoutExporter(metrics=[metric])
>>> exporter.start()
>>> # Your code
>>> exporter.stop()
>>>
>>> with exporter:
>>>     # Your code

