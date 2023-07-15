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

With Poetry
===========

.. code-block:: bash

    # Setup Python
    make init

    # List everything
    make help
