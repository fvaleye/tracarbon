# Enforce Conventional Commits and automate releases

* Status: Accepted
* Date: 2026-10-19
* Pull requests: [#550](https://github.com/fvaleye/tracarbon/pull/550), [#551](https://github.com/fvaleye/tracarbon/pull/551)

## Context and Problem Statement

Release notes and version bumps were prepared by hand, and commit messages followed no checked format.

## Considered Options

* Keep manual releases
* Enforce Conventional Commits and let release-please open release PRs

## Decision Outcome

Chosen option: "Enforce Conventional Commits and let release-please open release PRs", because the commit history then drives versions and changelogs.

A pre-commit hook checks commit messages, and the `pr-title` workflow checks pull request titles. Branch protection on `main` requires that check and the pre-commit `format` job. The `release-please` workflow opens release PRs on `main`. Merging one tags `vX.Y.Z` and creates the GitHub release, which runs `release.yml` (version check, build, PyPI, docs). The workflow authenticates with a personal access token (`RELEASE_PLEASE_TOKEN`) so that the tag triggers `release.yml`.

### Consequences

* Good, because every merged change lands in the changelog under its type
* Bad, because a non-conforming title blocks the pull request
* Bad, because the release flow depends on a personal access token that must be rotated
