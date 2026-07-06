"""
daemon/__init__.py — wicked-garden daemon package.

The daemon is a background service that:
- Monitors the wicked-bus event stream for garden-relevant events
- Manages council sessions (multi-model voting)
- Runs HITL (human-in-the-loop) hooks
- Maintains a projector for state projection
- Provides an HTTP server for the garden dashboard
"""
from __future__ import annotations

from daemon._internal import DaemonError, generate_id, now_iso
from daemon.db import get_connection
from daemon.server import create_app

__version__ = "0.1.0"

__all__ = [
    "Daemon",
    "start",
    "version",
    "__version__",
    "DaemonError",
    "generate_id",
    "now_iso",
    "get_connection",
    "create_app",
]


def version() -> str:
    """Return the daemon version string."""
    return __version__


class Daemon:
    """wicked-garden background daemon.

    Coordinates the event consumer, hook dispatcher, projector, and HTTP server
    into a single runnable unit.

    Usage::

        d = Daemon()
        d.start()           # blocking — runs until KeyboardInterrupt
        d.start(block=False) # non-blocking — returns after components start
        d.stop()            # signal all components to shut down
    """

    def __init__(
        self,
        db_path: str | None = None,
        hooks_dir: str | None = None,
        host: str = "127.0.0.1",
        port: int = 7700,
        poll_interval_ms: int = 5000,
    ) -> None:
        import threading
        from pathlib import Path

        from daemon.consumer import EventConsumer
        from daemon.hook_dispatch import HookDispatcher
        from daemon.projector import Projector
        from daemon.server import create_app

        self._host = host
        self._port = port
        self._stop_event = threading.Event()

        # DB
        self._conn = get_connection(db_path)

        # Components
        hooks_path = Path(hooks_dir) if hooks_dir else Path.cwd() / "hooks"
        self._projector = Projector(self._conn)
        self._dispatcher = HookDispatcher(self._conn, hooks_path)
        self._consumer = EventConsumer(
            self._conn,
            poll_interval_ms=poll_interval_ms,
            on_event=self._on_event,
        )
        self._app = create_app(self._conn, self._projector)

    def _on_event(self, event_type: str, payload: dict) -> None:
        """Internal callback wired from consumer to projector + dispatcher."""
        self._projector.update(event_type, payload)
        self._dispatcher.dispatch(event_type, payload)

    def start(self, block: bool = True) -> None:
        """Start all daemon components.

        Args:
            block: When True (default), runs the Flask dev server in the
                   foreground (blocks until Ctrl-C or stop()). When False,
                   starts the consumer thread and returns immediately — the
                   HTTP server is NOT started in non-blocking mode, which
                   is primarily useful for tests.
        """
        self._consumer.start()
        if block:
            try:
                self._app.run(host=self._host, port=self._port)
            finally:
                self.stop()

    def stop(self) -> None:
        """Signal all components to stop."""
        self._consumer.stop()
        self._stop_event.set()


def start(
    db_path: str | None = None,
    hooks_dir: str | None = None,
    host: str = "127.0.0.1",
    port: int = 7700,
) -> None:
    """Convenience entry-point. Creates a Daemon and starts it (blocking)."""
    daemon = Daemon(db_path=db_path, hooks_dir=hooks_dir, host=host, port=port)
    daemon.start(block=True)
