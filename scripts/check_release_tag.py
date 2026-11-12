"""Fail when a release tag does not match the package version.

The publish workflow runs this before it builds or uploads. A tag ``v0.2.2``
matches version ``0.2.2``. Anything else exits nonzero and prints the reason.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def package_version(pyproject: Path) -> str:
    """Return ``project.version`` from a pyproject file."""
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{pyproject} has no project.version")
    return version.strip()


def tag_version(tag: str) -> str:
    """Strip ``refs/tags/`` and a single leading ``v`` from a tag name."""
    name = tag.strip().removeprefix("refs/tags/")
    return name.removeprefix("v")


def check_release_tag(tag: str, version: str) -> str:
    """Return an error message when ``tag`` does not match ``version``."""
    if not tag.strip():
        return f"release tag is empty; expected v{version}"
    got = tag_version(tag)
    if got != version:
        shown = tag.strip()
        return (
            f"release tag {shown} does not match pyproject version {version}; expected v{version}"
        )
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a release tag against pyproject.toml")
    parser.add_argument("tag", help="Tag name, for example v0.2.2")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    args = parser.parse_args(argv)
    try:
        version = package_version(args.pyproject)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"release tag check failed: {exc}", file=sys.stderr)
        return 1
    message = check_release_tag(args.tag, version)
    if message:
        print(message, file=sys.stderr)
        return 1
    print(f"release tag {args.tag.strip()} matches pyproject version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
