"""Print a drift report across all cities.

Reads each cities/<code>/data/zero_yield_streak.json and prints, per city,
venues sorted by streak length (worst first). Highlights:

  ERROR   — first zero after a known-good history (streak == 1 AND last_nonzero_run set)
  WARN    — streak >= 3 consecutive zero builds
  cold    — streak >= 1 but never produced events (likely never worked / off-season seed)

Usage:  python tools/audit_venue_drift.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CITIES = REPO_ROOT / "cities"
WARN_AT = 3


def _load(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"  ! unreadable {p}: {exc}", file=sys.stderr)
        return {}


def main() -> int:
    any_finding = False
    for city_dir in sorted(CITIES.iterdir()):
        if not city_dir.is_dir():
            continue
        state_path = city_dir / "data" / "zero_yield_streak.json"
        state = _load(state_path)
        if not state:
            continue

        rows = []
        for vid, entry in state.items():
            streak = int(entry.get("streak", 0))
            last_ok = entry.get("last_nonzero_run")
            if streak <= 0:
                continue
            if streak == 1 and last_ok:
                level = "ERROR"
            elif streak >= WARN_AT:
                level = "WARN "
            elif not last_ok:
                level = "cold "
            else:
                level = "info "
            rows.append((level, streak, vid, last_ok or "(never)"))

        if not rows:
            continue
        any_finding = True
        # Sort: ERROR first, then by streak desc
        order = {"ERROR": 0, "WARN ": 1, "cold ": 2, "info ": 3}
        rows.sort(key=lambda r: (order[r[0]], -r[1]))

        print(f"\n=== {city_dir.name} ({len(rows)} drift row{'s' if len(rows)!=1 else ''}) ===")
        print(f"  {'level':<6} {'streak':>6}  {'venue_id':<40} last_nonzero_run")
        for level, streak, vid, last_ok in rows:
            print(f"  {level:<6} {streak:>6}  {vid:<40} {last_ok}")

    if not any_finding:
        print("No drift findings — every tracked venue produced events on its last build.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
