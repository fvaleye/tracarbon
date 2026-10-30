***********
Development
***********

Set up development
==================

From the repository root, install dependencies and enable commit hooks:

.. code-block:: bash

    make init
    uv run pre-commit install

Run ``make help`` to list available commands.

Run tests
=========

Run the full suite in parallel with coverage:

.. code-block:: bash

    make test-unit

Run a single test file:

.. code-block:: bash

    uv run python -m pytest tests/locations/test_location.py

Debug the previous run's failures, stopping at the first failure:

.. code-block:: bash

    uv run python -m pytest --lf -x --pdb --no-cov

Build documentation
===================

Build the site and start a local preview. Warnings fail the build, as in CI.

.. code-block:: bash

    make build-documentation
    uv run python -m http.server 8000 --bind 127.0.0.1 --directory docs/build/html

Open ``http://127.0.0.1:8000``. Rebuild after edits and refresh the page.
Press ``Ctrl+C`` to stop the preview.

Use Docker
==========

Build the image and open a development shell:

.. code-block:: bash

    docker build -t tracarbon .
    docker run --rm -it --entrypoint bash tracarbon

To measure with the container, pass options to its ``tracarbon run`` entrypoint:

.. code-block:: bash

    docker run --rm -e TRACARBON_INTERVAL_IN_SECONDS=1 tracarbon --country-code-alpha-iso-2 fr

Measurements require access to supported Linux sensors. Docker on macOS cannot
read the Mac's sensors; use a native installation to measure the Mac.

.. toctree::
   :maxdepth: 1

   decisions/index
