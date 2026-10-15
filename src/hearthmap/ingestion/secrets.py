"""Local credentials for authenticated sources (M1C.1).

Credentials come only from the process environment or the Git-ignored
``.env.local`` file. They are held in :class:`Secret`, whose ``repr``/``str``
never reveal the value, and every URL that may carry one is passed through
:func:`sanitize_url` before it is recorded anywhere (manifests, provenance,
logs, reports). Provenance records only *how* access happened, e.g.
``access_method: authenticated GISTDA API`` / ``credential_source: environment``.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

REDACTED = "REDACTED"
#: Query parameters treated as credentials wherever they appear in a URL.
SECRET_QUERY_PARAMS = frozenset(
    {"key", "api_key", "apikey", "api-key", "token", "access_token", "client_secret"}
)
DEFAULT_ENV_FILE = Path(".env.local")
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


class MissingCredentialError(RuntimeError):
    """The named credential is not configured (message never contains a value)."""


class Secret:
    """Opaque credential holder: the value is only available via :meth:`reveal`."""

    __slots__ = ("_value", "name")

    def __init__(self, name: str, value: str) -> None:
        if not value:
            raise MissingCredentialError(f"credential {name} is empty")
        self.name = name
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Secret({self.name}=<{REDACTED}>)"

    __str__ = __repr__

    def __reduce__(self):  # never pickle/serialise a credential
        raise TypeError("Secret values cannot be serialised")


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text("utf-8").splitlines():
        m = _LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


def load_secret(name: str, env_file: Path | None = DEFAULT_ENV_FILE) -> Secret:
    """Environment variable first, then ``env_file``; raise if neither has it."""
    value = os.environ.get(name) or (_read_env_file(Path(env_file)).get(name) if env_file else None)
    if not value:
        raise MissingCredentialError(
            f"credential {name} not found in the environment or {env_file}"
        )
    return Secret(name, value)


def credential_source(name: str) -> str:
    """Where a credential would come from, for provenance (never the value)."""
    return "environment" if os.environ.get(name) else "local environment file (.env.local)"


def sanitize_url(url: str) -> str:
    """Replace the value of every credential query parameter with ``REDACTED``."""
    parts = urllib.parse.urlsplit(url)
    if not parts.query:
        return url
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    clean = [(k, REDACTED if k.lower() in SECRET_QUERY_PARAMS else v) for k, v in pairs]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(clean)))


def is_sanitized(url: str) -> bool:
    """True when no credential query parameter carries a real value."""
    q = urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query, keep_blank_values=True)
    return all(v == REDACTED for k, v in q if k.lower() in SECRET_QUERY_PARAMS)


def scrub(text: str, secret: Secret) -> str:
    """Remove a credential value from arbitrary text (e.g. an exception message)."""
    return text.replace(secret.reveal(), REDACTED)
