"""Tests for Monitor: update() clears render-induced events to stop re-render loops."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from gitplot.monitor import Monitor


def _make_monitor(tmp_path: Path) -> Monitor:
    output_path = tmp_path / "gitplot.svg"
    return Monitor(repo_path=str(tmp_path), output_path=output_path)


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

        def fire():
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
    mon._handler._handle(str(output_path))
    assert not mon._event.is_set(), "Events on the output file must be filtered"


# ---------------------------------------------------------------------------
# New tests: targeted .git/index suppression replaces blanket drain
# ---------------------------------------------------------------------------


def test_update_clears_pending_events(tmp_path: Path) -> None:
    """update() must clear all pending events after a render.

    In verbose mode, get_index_state() reads .git/index, which triggers git's
    stat-cache refresh and sets the event DURING the render (before update() is
    called).  Without clearing, every render immediately re-triggers wait(), which
    triggers another render, causing an infinite loop.  Clearing here is safe
    because the render already captured the repo state that caused those events;
    any NEW user changes after the clear will set the event again normally.
    """
    mon = _make_monitor(tmp_path)
    mon._event.set()
    mon.update(frozenset(["node1"]), drain_seconds=0)
    assert not mon._event.is_set(), (
        "update() must clear pending events to break the render-induced re-trigger loop"
    )


def test_update_suppresses_git_index_events(tmp_path: Path) -> None:
    """After update(), events from .git/index are suppressed for drain_seconds."""
    mon = _make_monitor(tmp_path)
    mon.update(frozenset(), drain_seconds=10)  # long window so it stays open
    index_path = tmp_path / ".git" / "index"
    mon._handler._handle(str(index_path))
    assert not mon._event.is_set(), (
        ".git/index events must be suppressed immediately after update() "
        "to prevent GitPython stat-cache refresh from causing a re-render loop"
    )


def test_update_does_not_suppress_non_index_git_events(tmp_path: Path) -> None:
    """After update(), events from other .git files (e.g. refs) still fire."""
    mon = _make_monitor(tmp_path)
    mon.update(frozenset(), drain_seconds=10)  # long window
    refs_path = tmp_path / ".git" / "refs" / "heads" / "main"
    mon._handler._handle(str(refs_path))
    assert mon._event.is_set(), (
        "Non-index git events (e.g. commit refs) must not be suppressed — "
        "they represent real changes the user made"
    )


def test_index_suppression_expires(tmp_path: Path) -> None:
    """After drain_seconds elapses, .git/index events fire normally again."""
    mon = _make_monitor(tmp_path)
    mon.update(frozenset(), drain_seconds=0)  # suppress window is already expired
    index_path = tmp_path / ".git" / "index"
    mon._handler._handle(str(index_path))
    assert mon._event.is_set(), "An expired suppression window must not block .git/index events"


def test_wait_preserves_events_set_during_settle(tmp_path: Path) -> None:
    """Events that arrive during the settle window must not be drained.

    A 'git commit' immediately after 'git add' fires events during wait()'s
    settle period.  The old code cleared those at the end of the settle,
    causing the commit to be invisible until the next unrelated change.
    """
    mon = _make_monitor(tmp_path)
    settle = 0.1

    # Fire initial event so wait() wakes up, then fire a second one during settle.
    mon._event.set()

    def set_during_settle() -> None:
        time.sleep(settle / 2)
        mon._event.set()

    t = threading.Thread(target=set_during_settle, daemon=True)
    t.start()
    mon.wait(settle_seconds=settle)
    t.join(timeout=2)

    assert mon._event.is_set(), (
        "An event that arrived during the settle window must remain set "
        "so the monitor loop can re-render with the new commit"
    )
