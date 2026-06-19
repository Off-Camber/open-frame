# Publish to PyPI

This project is packaged as `off-camber-open-frame`.

## One-time setup

1. Ensure the package name exists or is available on PyPI.
2. In the GitHub repository, configure PyPI trusted publishing for this project:
   - PyPI project settings -> Publishing -> Add GitHub publisher
   - Owner/repo: `Off-Camber/open-frame`
   - Workflow: `publish-pypi.yml`
   - Environment (optional): leave empty unless your org requires one
3. Confirm `pyproject.toml` version is correct for the release.

## Local preflight checks

```bash
python -m pip install -e .[dev]
python -m pip install build twine
python -m pytest
python -m ruff check .
python -m build --sdist --wheel
python -m twine check dist/*
```

## Publish flow

Preferred path:

1. Create and publish a GitHub Release for the tag (for example `v0.1.0`).
2. The `Publish to PyPI` workflow runs automatically and uploads artifacts.

Manual path:

- Run the `Publish to PyPI` workflow from the Actions tab (`workflow_dispatch`).

## Verify release

- Confirm version and files on [PyPI](https://pypi.org/).
- Install in a clean environment:

```bash
pip install off-camber-open-frame==<version>
open-frame --help
```

## Notes

- Do not overwrite published versions; bump `project.version` for each release.
- Workflow reruns for an already-published version may return "file already exists"; the publish workflow is configured with `skip-existing: true` so reruns stay green.
- Keep `README.md` and metadata classifiers current so the PyPI page stays accurate.
