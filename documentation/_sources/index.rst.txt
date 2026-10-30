Tracarbon
=========

Tracarbon tracks your device's energy consumption and calculates its carbon
emissions. Use the CLI to measure a command or monitor your machine, or the Python
API to track a workload in your application.

This documentation covers version |release|.

Quick start
-----------

Install Tracarbon and start tracking:

.. code-block:: console

   pip install tracarbon
   tracarbon run

Press ``Ctrl+C`` to stop and print the report. No API key is required.
See :doc:`installation` for optional exporters.

See :doc:`usage` to measure a command, use the Python API, configure carbon
intensity, track processes, and export metrics.

Guides and reference
--------------------

.. toctree::
   :maxdepth: 1

   installation
   usage
   api_reference
   development


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
