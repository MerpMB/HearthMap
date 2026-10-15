"""RAW-stage acquisition: checksums, no overwrite, size guard, tamper detection.
Uses SYNTHETIC local files via file:// URLs (no network)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hearthmap.ingestion.acquire import (
    DownloadTooLargeError,
    RawIntegrityError,
    RawManifest,
    download,
    verify_raw,
)


def _src_file(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "artifact.bin"
    src.parent.mkdir()
    src.write_bytes(b"SYNTHETIC raw bytes")
    return src


def test_download_records_checksum_and_refuses_overwrite(tmp_path):
    src = _src_file(tmp_path)
    dest = tmp_path / "raw"
    art = download(src.as_uri(), dest)
    assert art.sha256 == hashlib.sha256(b"SYNTHETIC raw bytes").hexdigest()
    assert (dest / art.stored_path).read_bytes() == src.read_bytes()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        download(src.as_uri(), dest)


def test_size_guard_blocks_large_files(tmp_path):
    src = _src_file(tmp_path)
    with pytest.raises(DownloadTooLargeError):
        download(src.as_uri(), tmp_path / "raw", size_guard_bytes=5)


def test_verify_raw_detects_modification(tmp_path):
    src = _src_file(tmp_path)
    dest = tmp_path / "raw"
    art = download(src.as_uri(), dest)
    RawManifest(source_id="synthetic", version="v", artifacts=[art]).write(dest)
    assert verify_raw(dest).artifacts[0].sha256 == art.sha256
    (dest / art.stored_path).write_bytes(b"tampered")
    with pytest.raises(RawIntegrityError, match="changed since acquisition"):
        verify_raw(dest)


def test_verify_raw_detects_missing_file(tmp_path):
    src = _src_file(tmp_path)
    dest = tmp_path / "raw"
    art = download(src.as_uri(), dest)
    RawManifest(source_id="synthetic", version="v", artifacts=[art]).write(dest)
    (dest / art.stored_path).unlink()
    with pytest.raises(RawIntegrityError, match="missing"):
        verify_raw(dest)
