"""Monitor mode: watches the repo for changes and triggers re-renders.

Uses threading.Event for inter-thread signaling (no global state).
Filters out filesystem events caused by visigit's own output to prevent
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
        self._suppress_index_until: float = 0.0

    def suppress_index(self, duration: float) -> None:
        """Suppress .git/index events for duration seconds.

        GitPython's repo reads trigger git's stat-cache refresh, which writes
        .git/index.  Suppressing that file specifically (not all events) prevents
        a render from looping back on itself while still letting commit events
        (.git/refs/heads/*, COMMIT_EDITMSG, etc.) pass through immediately.
        """
        self._suppress_index_until = time.monotonic() + duration

    def _handle(self, event_path: str) -> None:
        abs_path = str(Path(event_path).resolve())
        if abs_path in self._ignore_paths:
            return
        p = Path(abs_path)
        if (
            p.name == "index"
            and p.parent.name == ".git"
            and time.monotonic() < self._suppress_index_until
        ):
            log.debug("Suppressed .git/index event (GitPython stat-cache noise)")
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
        ignore.add(str((output_path.parent / "visigit.html").resolve()))
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
        """Block until a change is detected, then let the repo settle.

        Events that arrive during the settle window are intentionally preserved:
        a 'git commit' immediately following 'git add' fires during this window,
        and draining it would cause the commit to be invisible until the next
        unrelated change.
        """
        self._event.wait()
        self._event.clear()
        time.sleep(settle_seconds)

    def update(self, node_ids: frozenset[str], drain_seconds: float = 0.3) -> None:
        """Record node IDs from the most recent render and reset the event state.

        Clears the event to remove noise that accumulated during the render:
        - settle-window residue (events from git-add that re-set the flag during
          the 500 ms settle, already captured by the render that just finished)
        - stat-cache updates (.git/index written by GitPython's index reads in
          verbose mode), which fire during the render and would cause an immediate
          spurious re-render if left set

        suppress_index() then guards against delayed stat-cache events that arrive
        after the clear but within drain_seconds.

        Any NEW user changes (git commit, git add, etc.) that happen after the
        clear will set the event again normally and be picked up by the next wait().
        """
        self.prev_node_ids = node_ids
        self._event.clear()
        self._handler.suppress_index(drain_seconds)
