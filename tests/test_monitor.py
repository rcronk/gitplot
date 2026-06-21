"""Tests for Monitor: post-render drain prevents self-induced re-render loops."""

from __future__ import annotations

import threading
from pathlib import Path

from gitplot.monitor import Monitor


def _make_monitor(tmp_path: Path) -> Monitor:
    output_path = tmp_path / "gitplot.svg"
    return Monitor(repo_path=str(tmp_path), output_path=output_path)


def test_monitor_update_drains_pending_event(tmp_path: Path) -> None:
    """update() clears any events that fired during rendering (drain_seconds=0)."""
    mon = _make_monitor(tmp_path)
    # Simulate a filesystem event that arrives while rendering
    mon._event.set()
    mon.update(frozenset(["node1"]), drain_seconds=0)
    assert not mon._event.is_set(), "update() must drain pending events so the loop does not spin"


def test_monitor_update_stores_node_ids(tmp_path: Path) -> None:
    """update() records the latest node IDs for highlight diffing."""
    mon = _make_monitor(tmp_path)
    ids = frozenset(["a", "b", "c"])
    mon.update(ids, drain_seconds=0)
    assert mon.prev_node_ids == ids


def test_monitor_wait_returns_after_event(tmp_path: Path) -> None:
    """wait() blocks until an event fires, then returns."""
    mon = _make_monitor(tmp_path)
    mon.start()
    try:
        # Fire an event from a background thread with a short delay
        def fire():
            import time

            time.sleep(0.05)
            mon._event.set()

        t = threading.Thread(target=fire, daemon=True)
        t.start()
        mon.wait(settle_seconds=0)  # zero settle so the test stays fast
        t.join(timeout=2)
    finally:
        mon.stop()


def test_monitor_ignores_output_path(tmp_path: Path) -> None:
    """Events for the output file itself are ignored to prevent self-triggering."""
    output_path = tmp_path / "gitplot.svg"
    mon = Monitor(repo_path=str(tmp_path), output_path=output_path)
    # Simulate an event on the output file
    mon._handler._handle(str(output_path))
    assert not mon._event.is_set(), "Events on the output file must be filtered"
