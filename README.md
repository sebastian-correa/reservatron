# reservatron  <!-- omit from toc -->

Simple app to reserve classes/spots in different places

## Table of contents <!-- omit from toc -->

<!--TOC-->

- [Development](#development)
  - [Setup](#setup)
  - [Dependency versions](#dependency-versions)

<!--TOC-->

## Development

### Setup

We use `uv` to manage packages and Python versions. To set up the repo for development,

1. Clone the repo.
2. `uv sync`.
3. `uv run pre-commit install`.

### Dependency versions

You can update `pre-commit` repos by running `pre-commit autoupdate`. Dependabot should take care of the rest of the dependencies.
