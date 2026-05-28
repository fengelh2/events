"""Persistent zero-yield tracker — catches silent scraper drift.

State file (per city): cities/<code>/data/zero_yield_streak.json
Shape:
    {
      "<venue_id>": {
        "streak": <int>,                 # consecutive builds returning 0 events
        "last_nonzero_run": "YYYY-MM-DD"  # ISO date of most recent build with >=1 event, or null
      },
      ...
    }

After each build the tracker is updated:
  - 0 events  → streak += 1
  - >0 events → streak = 0, last_nonzero_run = today

Two escalation levels:
  - WARNING  if streak >= STREAK_WARN_AT (3 consecutive zeros) — likely drift, not off-season
  - ERROR    if a venue with a recorded last_nonzero_run now returns 0 (a venue we KNOW
             used to produce events suddenly dried up — almost certainly broken)

This helper is intentionally self-contained: no scraper dependency, only stdlib +
the venue list / per-venue event counts that rebuild_calendar already computes.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Iterable

log = logging.getLogger("zero_yield_tracker")

STREAK_WARN_AT = 3
# Skip kinds that don't represent live scraping
_SKIP_KINDS = {"unknown", "static"}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as exc:
        log.warning("zero_yield_streak.json unreadable, resetting: %s", exc)
        return {}


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
    tmp.replace(path)


def update_and_alert(
    venues: Iterable[dict],
    venue_events: dict,
    state_path: Path,
    today: str | None = None,
) -> dict:
    """Update streak state on disk + emit warnings/errors. Returns the new state.

    venue_events: {venue_id: int_event_count}  (already computed by rebuild_calendar)
    state_path:   cities/<code>/data/zero_yield_streak.json
    """
    today = today or date.today().isoformat()
    state = _load(state_path)

    drift_warn: list[tuple[str, str, int]] = []      # streak >= STREAK_WARN_AT
    sudden_dry: list[tuple[str, str, str]] = []      # had last_nonzero_run, now 0

    tracked_ids: set[str] = set()
    for v in venues:
        vid = v.get("id")
        kind = v.get("kind", "unknown")
        if not vid or kind in _SKIP_KINDS:
            continue
        tracked_ids.add(vid)
        n = int(venue_events.get(vid, 0))
        entry = state.get(vid) or {"streak": 0, "last_nonzero_run": None}
        prior_nonzero = entry.get("last_nonzero_run")

        if n > 0:
            entry["streak"] = 0
            entry["last_nonzero_run"] = today
        else:
            entry["streak"] = int(entry.get("streak", 0)) + 1
            if prior_nonzero and entry["streak"] == 1:
                # First zero after a known-good history → strongest drift signal.
                sudden_dry.append((vid, kind, prior_nonzero))
            if entry["streak"] >= STREAK_WARN_AT:
                drift_warn.append((vid, kind, entry["streak"]))

        state[vid] = entry

    # Drop venues no longer in the config (renamed / removed) to keep the file tidy.
    for stale in [k for k in state.keys() if k not in tracked_ids]:
        state.pop(stale, None)

    _save(state_path, state)

    if sudden_dry:
        log.error(
            "DRIFT: %d venue(s) had prior events but returned 0 today (likely broken): %s",
            len(sudden_dry),
            ", ".join(f"{vid}({kind}, last_ok={d})" for vid, kind, d in sudden_dry),
        )
    if drift_warn:
        log.warning(
            "DRIFT: %d venue(s) have returned 0 events for >=%d consecutive builds: %s",
            len(drift_warn),
            STREAK_WARN_AT,
            ", ".join(f"{vid}({kind}, streak={s})" for vid, kind, s in drift_warn),
        )

    return state
