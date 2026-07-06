"""
_internal.py — Internal utilities shared across daemon modules.

Provides:
- generate_id()       → UUID4 string
- now_iso()           → ISO 8601 UTC timestamp string
- emit_bus_event()    → fire-and-forget subprocess call to npx wicked-bus emit
- DaemonError         → base exception class for daemon errors
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("wicked-garden.daemon")


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class DaemonError(Exception):
    """Base exception for wicked-garden daemon errors."""


class DaemonConfigError(DaemonError):
    """Raised when the daemon is misconfigured."""


class DaemonDBError(DaemonError):
    """Raised when a database operation fails."""


# ---------------------------------------------------------------------------
# ID / timestamp helpers
# ---------------------------------------------------------------------------


def generate_id() -> str:
    """Return a new UUID4 as a plain string."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Example: ``2026-07-04T12:34:56.789012+00:00``
    """
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Bus event emission
# ---------------------------------------------------------------------------

_BUS_TIMEOUT_S = 5


def emit_bus_event(
    event_type: str,
    domain: str,
    subdomain: str,
    payload_dict: dict[str, Any],
    idempotency_key: str | None = None,
) -> None:
    """Emit an event to wicked-bus. Fire-and-forget.

    Spawns a background thread so the caller is never blocked. If the bus is
    not available (npx not found, non-zero exit), the error is logged at DEBUG
    level and silently ignored — graceful degradation.

    Args:
        event_type: The bus event type string, e.g. ``wicked.garden.event``.
        domain: Bus domain, e.g. ``wicked-garden``.
        subdomain: Bus subdomain, e.g. ``garden.council``.
        payload_dict: Arbitrary JSON-serialisable dict.
        idempotency_key: Optional idempotency key forwarded as
            ``--idempotency-key`` to ``wicked-bus emit``.
    """

    def _fire() -> None:
        try:
            payload_str = json.dumps(payload_dict, default=str)
            cmd = [
                "npx",
                "wicked-bus",
                "emit",
                "--type", event_type,
                "--domain", domain,
                "--subdomain", subdomain,
                "--payload", payload_str,
                "--json",
            ]
            if idempotency_key is not None:
                cmd.extend(["--idempotency-key", idempotency_key])
            subprocess.run(
                cmd,
                timeout=_BUS_TIMEOUT_S,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            # npx not available — silently skip
            logger.debug("wicked-bus not available (npx not found); skipping emit for %s", event_type)
        except subprocess.TimeoutExpired:
            logger.debug("wicked-bus emit timed out for event %s", event_type)
        except Exception as exc:  # noqa: BLE001
            logger.debug("wicked-bus emit failed for %s: %s", event_type, exc)

    threading.Thread(target=_fire, daemon=True).start()
