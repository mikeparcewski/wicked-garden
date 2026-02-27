#!/usr/bin/env python3
"""
_control_plane.py — HTTP client for the wicked-control-plane backend.

Stdlib-only (urllib.request). Importable by both hook scripts (strict
stdlib-only constraint) and command scripts.

URL convention:
    {endpoint}/api/{api_version}/data/{domain}/{source}/{verb}[/{id}]

Domain name mapping:
    Callers can use either plugin names (wicked-mem) or CP domain names
    (memory). The client normalizes automatically.

Example calls:
    cp = ControlPlaneClient()
    cp.request("memory", "memories", "list", params={"project": "my-proj"})
    cp.request("kanban", "tasks", "create", payload={"subject": "..."})
    cp.request("wicked-mem", "memories", "list")  # also works
    cp.manifest()                                  # full API manifest
    cp.manifest_detail("memory", "memories", "create")  # endpoint detail
    ok, version = cp.check_health()
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"

_DEFAULT_CONFIG: dict[str, Any] = {
    "endpoint": "http://localhost:18889",
    "auth_token": None,
    "api_version": "v1",
    "health_check_interval_seconds": 60,
    "connect_timeout_seconds": 3,
    "request_timeout_seconds": 10,
    "setup_complete": False,
}

# ---------------------------------------------------------------------------
# Domain name mapping: plugin names → CP domain names
# ---------------------------------------------------------------------------

_DOMAIN_MAP: dict[str, str] = {
    "wicked-mem": "memory",
    "wicked-kanban": "kanban",
    "wicked-crew": "crew",
    "wicked-jam": "jam",
    "wicked-delivery": "delivery",
    "wicked-search": "knowledge",
    "wicked-observability": "observability",
    "wicked-smaht": "smaht",
    "wicked-startah": "startah",
    # Bare names pass through unchanged
    "memory": "memory",
    "kanban": "kanban",
    "crew": "crew",
    "jam": "jam",
    "delivery": "delivery",
    "knowledge": "knowledge",
    "events": "events",
    "agents": "agents",
    "indexing": "indexing",
}

# HTTP method inference based on verb name (matches CP's manifest.ts)
_POST_VERBS = frozenset({
    "create", "ingest", "bulk-update", "bulk-delete", "archive",
    "unarchive", "sweep", "register", "heartbeat", "capture",
    "evaluate", "advance",
})
_PUT_VERBS = frozenset({"update"})
_DELETE_VERBS = frozenset({"delete"})


def _resolve_domain(domain: str) -> str:
    """Normalize a domain name to the CP's expected value."""
    return _DOMAIN_MAP.get(domain, domain)


def _infer_method(verb: str, has_payload: bool) -> str:
    """Infer HTTP method from verb name, matching CP conventions."""
    if verb in _POST_VERBS:
        return "POST"
    if verb in _PUT_VERBS:
        return "PUT"
    if verb in _DELETE_VERBS:
        return "DELETE"
    # Fallback: POST if payload provided, GET otherwise
    return "POST" if has_payload else "GET"


def _load_config() -> dict[str, Any]:
    """Load config from disk, merging with defaults for missing keys."""
    if not _CONFIG_PATH.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        raw = _CONFIG_PATH.read_text(encoding="utf-8")
        on_disk = json.loads(raw)
        merged = dict(_DEFAULT_CONFIG)
        merged.update(on_disk)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    """Atomically write config to disk."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CONFIG_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
        os.replace(tmp, _CONFIG_PATH)
    except OSError as exc:
        print(f"[wicked-garden] Failed to save config: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ControlPlaneClient:
    """Zero-external-dependency HTTP client for the wicked-control-plane.

    Timeouts:
        Hooks: 2-3s connect timeout (set via connect_timeout override).
        Commands: 10s request timeout (default from config).

    Retry:
        Commands: one silent retry after 500ms on connection error only.
        Hooks: no retry (hard timeout budget).
    """

    def __init__(self, *, hook_mode: bool = False):
        """
        Args:
            hook_mode: When True, use the shorter connect timeout and disable
                       retries. Hooks must never block the user.
        """
        self._cfg = _load_config()
        self._hook_mode = hook_mode

        # Timeouts (seconds)
        self._connect_timeout = (
            2 if hook_mode else self._cfg.get("connect_timeout_seconds", 3)
        )
        self._request_timeout = (
            2 if hook_mode else self._cfg.get("request_timeout_seconds", 10)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request(
        self,
        domain: str,
        source: str,
        verb: str,
        *,
        id: str | None = None,
        payload: dict | None = None,
        params: dict | None = None,
    ) -> dict | None:
        """Execute a REST call against the control plane.

        Maps to: {endpoint}/api/{api_version}/data/{domain}/{source}/{verb}[/{id}]

        Domain names are normalized automatically — callers can use either
        plugin names (wicked-mem) or CP domain names (memory).

        HTTP method is inferred from the verb name to match CP conventions
        (create→POST, update→PUT, delete→DELETE, list/get/search→GET).

        Args:
            domain:  Plugin or CP domain (e.g. "wicked-mem" or "memory").
            source:  Resource collection (e.g. "memories", "tasks").
            verb:    CRUD verb ("list", "get", "create", "update", "delete").
            id:      Optional resource ID appended to the path.
            payload: JSON body for create/update.
            params:  URL query params for list/get.

        Returns:
            Parsed response dict (the full {data, meta} envelope), or None on
            any failure. Callers should treat None as "use fallback".
        """
        endpoint = self._cfg.get("endpoint")
        if not endpoint:
            return None

        cp_domain = _resolve_domain(domain)
        api_version = self._cfg.get("api_version", "v1")
        path = f"/api/{api_version}/data/{cp_domain}/{source}/{verb}"
        if id is not None:
            path = f"{path}/{id}"

        url = f"{endpoint.rstrip('/')}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        method = _infer_method(verb, payload is not None)
        return self._do_request(url, method=method, payload=payload)

    def manifest(self) -> dict | None:
        """Fetch the full API manifest from GET /api/v1/manifest.

        Returns:
            Manifest dict with domains, sources, verbs, or None on failure.
        """
        endpoint = self._cfg.get("endpoint")
        if not endpoint:
            return None

        api_version = self._cfg.get("api_version", "v1")
        url = f"{endpoint.rstrip('/')}/api/{api_version}/manifest"
        return self._do_request(url, method="GET", payload=None)

    def manifest_detail(
        self, domain: str, source: str, verb: str
    ) -> dict | None:
        """Fetch endpoint detail from GET /api/v1/manifest/{domain}/{source}/{verb}.

        Returns:
            EndpointDetail dict with method, path, parameters, request_body,
            response schema, or None on failure.
        """
        endpoint = self._cfg.get("endpoint")
        if not endpoint:
            return None

        cp_domain = _resolve_domain(domain)
        api_version = self._cfg.get("api_version", "v1")
        url = (
            f"{endpoint.rstrip('/')}/api/{api_version}/manifest"
            f"/{cp_domain}/{source}/{verb}"
        )
        return self._do_request(url, method="GET", payload=None)

    def query(self, sql: str) -> dict | None:
        """Execute a SELECT query via POST /api/v1/query.

        Args:
            sql: A SELECT-only SQL statement.

        Returns:
            Query result dict, or None on failure.
        """
        endpoint = self._cfg.get("endpoint")
        if not endpoint:
            return None

        api_version = self._cfg.get("api_version", "v1")
        url = f"{endpoint.rstrip('/')}/api/{api_version}/query"
        return self._do_request(url, method="POST", payload={"sql": sql})

    def check_health(self) -> tuple[bool, str]:
        """Ping GET /health and return (ok, version).

        The control plane exposes its health at /health (not /api/v1/health).
        Version mismatch is a soft warning — (True, version) is still returned
        so the session degrades gracefully rather than blocking the user.

        Returns:
            (ok: bool, version: str). ok=False on timeout or non-2xx response.
        """
        endpoint = self._cfg.get("endpoint")
        if not endpoint:
            return False, ""

        url = f"{endpoint.rstrip('/')}/health"

        result = self._do_request(url, method="GET", payload=None)
        if result is None:
            return False, ""

        status = result.get("status", "")
        version = result.get("version", "")

        if status not in ("ok", "healthy"):
            return False, version

        # Soft version warning — doesn't block
        expected = str(self._cfg.get("api_version", "v1"))
        if version and not version.startswith(expected.lstrip("v")):
            print(
                f"[wicked-garden] Control plane version {version!r} may not be "
                f"fully compatible with configured api_version {expected!r}.",
                file=sys.stderr,
            )

        return True, version

    def verify_and_save(self, endpoint: str, auth_token: str | None) -> tuple[bool, str]:
        """Verify connectivity to endpoint and save config on success.

        Called by the setup command. Does NOT read from the existing config —
        uses the provided endpoint and token directly.

        Args:
            endpoint:   Base URL, e.g. "http://localhost:18889".
            auth_token: Bearer token string, or None for local instances.

        Returns:
            (ok: bool, message: str) — message contains version on success
            or an error description on failure.
        """
        endpoint = endpoint.rstrip("/")
        cfg = _load_config()
        cfg["endpoint"] = endpoint
        cfg["auth_token"] = auth_token

        # Temporarily apply provided credentials for this probe
        old_cfg = self._cfg
        self._cfg = cfg
        ok, version = self.check_health()
        self._cfg = old_cfg

        if not ok:
            return False, f"Could not connect to {endpoint}. Check the URL and try again."

        # Persist
        cfg["setup_complete"] = True
        save_config(cfg)
        return True, version

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        token = self._cfg.get("auth_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _do_request(
        self,
        url: str,
        method: str,
        payload: dict | None,
        *,
        _retry: bool = True,
    ) -> dict | None:
        """Make a single HTTP request with optional one-shot retry.

        Auth header is never echoed in error output (security requirement).
        """
        headers = self._build_headers()
        body = json.dumps(payload).encode() if payload is not None else None

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self._request_timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)

        except urllib.error.HTTPError as exc:
            # 4xx/5xx — no retry, log (without auth header) and return None
            print(
                f"[wicked-garden] Control plane HTTP {exc.code} for "
                f"{method} {url}: {exc.reason}",
                file=sys.stderr,
            )
            return None

        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            # Connection / timeout error — one retry after 500ms for commands
            if not self._hook_mode and _retry:
                time.sleep(0.5)
                return self._do_request(url, method, payload, _retry=False)

            print(
                f"[wicked-garden] Control plane unreachable: {exc}",
                file=sys.stderr,
            )
            return None

        except json.JSONDecodeError as exc:
            print(
                f"[wicked-garden] Control plane returned invalid JSON: {exc}",
                file=sys.stderr,
            )
            return None


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def get_client(*, hook_mode: bool = False) -> ControlPlaneClient:
    """Return a configured ControlPlaneClient.

    Pass hook_mode=True from hook scripts to apply the shorter timeout budget.
    """
    return ControlPlaneClient(hook_mode=hook_mode)


def load_config() -> dict[str, Any]:
    """Public accessor for config (used by bootstrap and setup)."""
    return _load_config()


def resolve_domain(domain: str) -> str:
    """Public accessor for domain name resolution."""
    return _resolve_domain(domain)
