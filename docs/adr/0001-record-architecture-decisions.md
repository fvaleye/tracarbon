# Record architecture decisions

* Status: Accepted
* Date: 2026-10-19

## Context and Problem Statement

Design choices in Tracarbon live in pull request threads and commit history. Contributors and AI coding agents cannot find the reasons behind them, and risk reversing them by accident.

## Considered Options

* Keep the reasons in pull request descriptions only
* Write ADRs as Markdown files in the repository

## Decision Outcome

Chosen option: "Write ADRs as Markdown files in the repository", because they are versioned and reviewed with the code, and agents read them like any other file.

We follow the [MADR 4.0.0](https://github.com/adr/madr/tree/4.0.0) minimal template and `NNNN-title-with-dashes.md` naming, in [docs/adr](README.md). Accepted ADRs are not edited. A new ADR supersedes them. [AGENTS.md](../../AGENTS.md) tells coding agents to read the relevant ADRs before changing an area and to add or supersede one for a significant decision.

### Consequences

* Good, because decisions stay next to the code they constrain
* Good, because the same files serve humans and agents
* Bad, because contributors must judge what is significant and keep the index current
