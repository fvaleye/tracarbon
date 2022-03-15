***********
Development
***********

With Docker
===========
.. code-block:: bash

    # Inside the root folder
    docker build -t tracarbon ./

    # Build with Docker
    docker run -it tracarbon bash

With poetry
===============
.. code-block:: bash

    # Setup Python
    make setup

    # List everything
    make help