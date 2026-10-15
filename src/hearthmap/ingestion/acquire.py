"""Raw-artifact acquisition with an integrity manifest.

Pipeline stage RAW (docs/architecture/data-lifecycle.md): files are stored
exactly as downloaded under ``data/raw/<source_id>/<version>/`` together with
``manifest.json`` recording where they came from, when, their checksum and the
licence/metadata captured at acquisition time. RAW files are never modified;
later stages write elsewhere.
"""

from __future__ import annotations

import shutil
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hearthmap.ingestion.secrets import is_sanitized
from hearthmap.provenance.model import sha256_file

MANIFEST_NAME = "manifest.json"
DEFAULT_SIZE_GUARD_BYTES = 250 * 1024 * 1024
_USER_AGENT = "HearthMap/0.1 (local research; contact via repository owner)"


class RawArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_filename: str
    stored_path: str
    source_url: str
    final_url: str | None = None
    acquired_at: datetime
    size_bytes: int
    sha256: str
    http_headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("source_url", "final_url")
    @classmethod
    def _no_credentials(cls, v: str | None) -> str | None:
        if v is not None and not is_sanitized(v):
            raise ValueError("URL carries a credential; record sanitize_url(url) instead")
        return v


class RawManifest(BaseModel):
    """Everything needed to trust (or re-acquire) a raw source version."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    source_id: str
    version: str
    landing_page: str | None = None
    licence: str | None = None
    licence_url: str | None = None
    publisher_metadata: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    artifacts: list[RawArtifact] = Field(default_factory=list)

    def write(self, directory: Path) -> Path:
        path = Path(directory) / MANIFEST_NAME
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read(cls, directory: Path) -> RawManifest:
        return cls.model_validate_json((Path(directory) / MANIFEST_NAME).read_text("utf-8"))


class RawIntegrityError(RuntimeError):
    """A raw artifact no longer matches its recorded checksum or size."""


class DownloadTooLargeError(RuntimeError):
    """Remote file exceeds the acquisition size guard."""


def raw_dir(data_root: Path, source_id: str, version: str) -> Path:
    return Path(data_root) / "raw" / source_id / version


def download(
    url: str,
    dest_dir: Path,
    *,
    filename: str | None = None,
    size_guard_bytes: int | None = DEFAULT_SIZE_GUARD_BYTES,
    timeout: float = 600,
) -> RawArtifact:
    """Download ``url`` into ``dest_dir`` without altering the bytes.

    Refuses to overwrite an existing file (RAW is immutable) and refuses files
    whose declared size exceeds ``size_guard_bytes``.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        headers = {k: v for k, v in resp.headers.items()}
        declared = resp.headers.get("Content-Length")
        if size_guard_bytes is not None and declared and int(declared) > size_guard_bytes:
            raise DownloadTooLargeError(
                f"{url} declares {int(declared):,} bytes > guard {size_guard_bytes:,}; "
                "look for a spatial subset or tiled request first"
            )
        name = (
            filename
            or PurePosixPath(urllib.parse.unquote(urllib.parse.urlparse(resp.url).path)).name
        )
        target = dest_dir / name
        if target.exists():
            raise FileExistsError(f"refusing to overwrite raw artifact {target}")
        tmp = target.with_name(target.name + ".part")
        with tmp.open("wb") as fh:
            shutil.copyfileobj(resp, fh, length=1 << 20)
        final_url = resp.url
    tmp.rename(target)
    return RawArtifact(
        original_filename=name,
        stored_path=target.name,
        source_url=url,
        final_url=final_url if final_url != url else None,
        acquired_at=datetime.now(UTC),
        size_bytes=target.stat().st_size,
        sha256=sha256_file(target),
        http_headers={
            k: v
            for k, v in headers.items()
            if k.lower() in {"content-length", "content-type", "last-modified", "etag"}
        },
    )


def register_existing(path: Path, *, source_url: str, acquired_at: datetime) -> RawArtifact:
    """Describe a file that was already downloaded by another tool."""
    path = Path(path)
    return RawArtifact(
        original_filename=path.name,
        stored_path=path.name,
        source_url=source_url,
        acquired_at=acquired_at,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def verify_raw(directory: Path) -> RawManifest:
    """Re-hash every artifact listed in the manifest; raise on any mismatch."""
    directory = Path(directory)
    manifest = RawManifest.read(directory)
    for art in manifest.artifacts:
        path = directory / art.stored_path
        if not path.is_file():
            raise RawIntegrityError(f"missing raw artifact: {path}")
        if path.stat().st_size != art.size_bytes or sha256_file(path) != art.sha256:
            raise RawIntegrityError(f"raw artifact changed since acquisition: {path}")
    return manifest
