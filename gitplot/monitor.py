"""Monitor mode: watches the repo for changes and triggers re-renders.

Uses threading.Event for inter-thread signaling (no global state).
Filters out filesystem events caused by gitplot's own output to prevent
self-triggering loops.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

log = logging.getLogger(__name__)


class _RepoEventHandler(FileSystemEventHandler):
    """Sets an Event when any relevant filesystem change occurs."""

    def __init__(self, change_event: threading.Event, ignore_paths: set[str]) -> None:
        super().__init__()
        self._event = change_event
        self._ignore_paths = ignore_paths  # absolute path strings to skip

    def _handle(self, event_path: str) -> None:
        abs_path = str(Path(event_path).resolve())
        if abs_path in self._ignore_paths:
            return
        log.debug("Change detected: %s", event_path)
        self._event.set()

    def on_moved(self, event) -> None:
        self._handle(event.dest_path)

    def on_created(self, event) -> None:
        self._handle(event.src_path)

    def on_deleted(self, event) -> None:
        self._handle(event.src_path)

    def on_modified(self, event) -> None:
        self._handle(event.src_path)


class Monitor:
    """Encapsulates the watch loop for monitor mode.

    Usage::

        monitor = Monitor(repo_path, output_path)
        monitor.start()
        while True:
            monitor.wait()          # blocks until a change is detected
            new_node_ids = render_fn(monitor.prev_node_ids)
            monitor.update(new_node_ids)
    """

    def __init__(self, repo_path: str, output_path: Path) -> None:
        self.repo_path = repo_path
        self.output_path = output_path
        self.prev_node_ids: frozenset[str] = frozenset()

        self._event = threading.Event()
        ignore = {str(output_path.resolve())}
        # Also ignore the companion HTML viewer file
        ignore.add(str((output_path.parent / "gitplot.html").resolve()))
        self._handler = _RepoEventHandler(self._event, ignore)
        self._observer: Optional[Observer] = None

    def start(self) -> None:
        """Start the filesystem observer."""
        self._observer = Observer()
        self._observer.schedule(self._handler, self.repo_path, recursive=True)
        self._observer.start()
        log.info("Monitor started on %s", self.repo_path)

    def stop(self) -> None:
        """Stop the filesystem observer."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def wait(self, settle_seconds: float = 0.5) -> None:
        """Block until a change is detected, then let the repo settle."""
        self._event.wait()
        self._event.clear()
        # Wait briefly for any rapid burst of events to finish
        time.sleep(settle_seconds)
        # Drain any events that fired during the settle window
        self._event.clear()

    def update(self, node_ids: frozenset[str], drain_seconds: float = 0.3) -> None:
        """Record node IDs from the most recent render and drain self-induced events.

        GitPython read operations (e.g. index diff) can trigger git's stat-cache
        refresh, which writes .git/index and fires a watchdog event.  Sleeping
        briefly after the render lets those events arrive, then clearing the flag
        prevents them from spuriously re-triggering the loop.
        """
        self.prev_node_ids = node_ids
        time.sleep(drain_seconds)
        self._event.clear()
