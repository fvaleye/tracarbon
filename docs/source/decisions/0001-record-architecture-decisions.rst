Record architecture decisions
=============================

:Status: Accepted
:Date: 2026-10-30

Context
-------

Tracarbon's choices about measurement and carbon estimates are explained across
pull requests. Contributors need a place to find the reasoning before changing
those choices. The project already publishes reStructuredText through Sphinx.

Decision
--------

Record only major, lasting design choices in ``docs/source/decisions/`` using
short, numbered reStructuredText files. Use the scope and template in :doc:`index`,
based on `Michael Nygard's ADR format
<https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>`_.

Review each record with the change it explains. Keep the original rationale when
a later decision supersedes it. Keep routine implementation and maintenance
decisions in pull requests.

Use the existing strict Sphinx build in GitHub Actions and pre-commit to check
markup and internal references.

Alternatives
------------

* Pull request descriptions alone preserve discussion but provide no decision index.
* Markdown ADRs would need a parser to appear in the existing Sphinx site.
* Dedicated ADR tooling offers structured validation but adds dependencies and
  configuration beyond the documentation checks we need initially.

Consequences
------------

Decisions are versioned with the code and searchable in the published docs.
Numbered records appear in the index automatically, without new dependencies.
Contributors maintain their status and links. Reviewers assess the reasoning
and whether a change needs an ADR; the build does not enforce those judgments.
