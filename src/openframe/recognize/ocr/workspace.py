"""Scratch files for Tesseract.

Leptonica 1.87 rewrites any path that starts with ``/tmp`` to the Darwin
per-user temp directory from ``confstr(_CS_DARWIN_USER_TEMP_DIR)``. With
``TMPDIR`` unset, Python writes the image under the real ``/tmp``
(``/private/tmp``), so Tesseract opens a path where the file is not. Scratch
files live under ``~/.openframe/tmp``, which Leptonica does not rewrite.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def ocr_scratch_root() -> Path:
    """Return Open Frame's OCR scratch directory, creating it when needed."""
    path = Path.home() / ".openframe" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def ocr_scratch_dir() -> Iterator[Path]:
    """Point ``tempfile`` at the OCR scratch directory for one read."""
    directory = ocr_scratch_root()
    previous = tempfile.tempdir
    tempfile.tempdir = str(directory)
    try:
        yield directory
    finally:
        tempfile.tempdir = previous
