Architecture decisions
======================

Architecture decision records (ADRs) explain major, lasting choices in Tracarbon's
design. Use one when a decision sets constraints across the project or would be
costly to reverse, such as choosing an energy accounting model or boundaries
between major components. Explain realistic alternatives and their tradeoffs.

Routine fixes, refactors, small API changes, and dependency or tooling updates
belong in pull requests. Read relevant accepted ADRs before changing the design.

.. toctree::
   :maxdepth: 1
   :glob:

   [0-9]*

Add a decision
--------------

Create ``NNNN-short-title.rst`` here with the next unused number and the template
below. The index includes numbered records automatically. Keep one decision per
record and link supporting issues, pull requests, or documentation.

Use ``Proposed`` while discussing a decision, then ``Accepted`` or ``Rejected``
after review. To replace an accepted decision, add a new record, mark the old one
``Superseded``, and link both with ``Supersedes`` and ``Superseded by``. Preserve
the original rationale.

Run ``make build-documentation`` to check the result. The same build runs in
GitHub Actions and the documentation pre-commit hook.

.. code-block:: rst

   Decision title
   ==============

   :Status: Proposed
   :Date: YYYY-MM-DD

   Context
   -------

   What problem or constraint requires a decision?

   Decision
   --------

   What do we choose, and why?

   Alternatives
   ------------

   Which realistic options did we reject, and why?

   Consequences
   ------------

   What improves, what costs more, and what constraints remain?
