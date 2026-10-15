"""Paged, attribute-filtered extraction from public ArcGIS REST layers.

Each response page is stored byte-for-byte as a RAW artifact (one JSON file per
page) so the subset can be re-verified later. Filtering happens server-side
(``where`` clause) to request only the area of interest instead of a national
dataset.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hearthmap.ingestion.acquire import _USER_AGENT, RawArtifact
from hearthmap.provenance.model import sha256_file


class ArcGISError(RuntimeError):
    """The service returned an error payload or an incomplete page sequence."""


def _get(url: str, params: dict[str, Any], timeout: float) -> bytes:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def query_count(
    layer_url: str, where: str, *, timeout: float = 120, extra_params: dict[str, Any] | None = None
) -> int:
    params = {"where": where, "returnCountOnly": "true", "f": "json", **(extra_params or {})}
    body = json.loads(_get(f"{layer_url}/query", params, timeout))
    if "error" in body:
        raise ArcGISError(str(body["error"]))
    return int(body["count"])


def fetch_pages(
    layer_url: str,
    *,
    where: str,
    out_fields: Sequence[str] | str,
    order_by: str,
    dest_dir: Path,
    prefix: str,
    page_size: int = 1000,
    pause_s: float = 0.3,
    timeout: float = 180,
    retries: int = 3,
    paginate: bool = True,
    extra_params: dict[str, Any] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[RawArtifact], int]:
    """Download all features matching ``where`` as raw JSON pages.

    Returns (artifacts, feature_count). Verifies the number of features
    received equals the server's count for the same query. With
    ``paginate=False`` (services without pagination support) a single request
    is made and the expected count must fit in one page.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    fields = out_fields if isinstance(out_fields, str) else ",".join(out_fields)
    expected = query_count(layer_url, where, timeout=timeout, extra_params=extra_params)
    artifacts: list[RawArtifact] = []
    received = 0
    offset = 0
    page = 0
    if not paginate and expected > page_size:
        raise ArcGISError(f"{expected} features exceed one page ({page_size}) without pagination")
    while offset < expected:
        params: dict[str, Any] = {
            "where": where,
            "outFields": fields,
            "orderByFields": order_by,
            "returnGeometry": "true",
            "f": "json",
        }
        params |= extra_params or {}
        if paginate:
            params |= {"resultOffset": offset, "resultRecordCount": page_size}
        for attempt in range(retries):
            try:
                raw = _get(f"{layer_url}/query", params, timeout)
                body = json.loads(raw)
                if "error" in body:
                    raise ArcGISError(str(body["error"]))
                break
            except (OSError, ArcGISError, json.JSONDecodeError):
                if attempt == retries - 1:
                    raise
                time.sleep(2 * (attempt + 1))
        n = len(body.get("features", []))
        if n == 0:
            break
        target = dest_dir / f"{prefix}_{page:05d}.json"
        if target.exists():
            raise FileExistsError(f"refusing to overwrite raw artifact {target}")
        target.write_bytes(raw)
        artifacts.append(
            RawArtifact(
                original_filename=target.name,
                stored_path=target.name,
                source_url=f"{layer_url}/query?{urllib.parse.urlencode(params)}",
                acquired_at=datetime.now(UTC),
                size_bytes=target.stat().st_size,
                sha256=sha256_file(target),
            )
        )
        received += n
        offset += n
        page += 1
        if progress:
            progress(received, expected)
        time.sleep(pause_s)
    if received != expected:
        raise ArcGISError(f"received {received} features but server reported {expected}")
    return artifacts, received


def layer_metadata(layer_url: str, *, timeout: float = 60) -> dict[str, Any]:
    return json.loads(_get(layer_url, {"f": "json"}, timeout))
