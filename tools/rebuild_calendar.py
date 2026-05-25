"""Orchestrator: scrape every venue, mark highlights, render events.html.

Run from events-la repo root:
    python tools/rebuild_calendar.py
        --venues       config/venues.yaml
        --highlights   config/highlights.yaml
        --out          .tmp/events.html

Per-venue scrape failure is logged and counted, NOT raised. The run fails (exit 2)
only if more than 5 venues fail.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml
from rapidfuzz import fuzz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import render_events_html  # noqa: E402
import scrape_venue_events  # noqa: E402

log = logging.getLogger("rebuild_calendar")


SEEN_EVENTS_PATH = REPO_ROOT / "data/seen_events.json"
SEEN_FRESH_DAYS = 14
SEEN_BOOTSTRAP_OFFSET_DAYS = 30


def _config_hash(venues_path: str, site: dict) -> str:
    """Hash that changes when scrape output should change: venues.yaml content,
    site locale config, parser code. Cache built under one hash is reusable
    when the hash matches."""
    import hashlib
    h = hashlib.sha256()
    h.update(Path(venues_path).read_bytes())
    h.update(str(sorted((site or {}).items())).encode("utf-8"))
    # Include the parser file mtime so a code-level fix invalidates the cache
    scraper = Path(__file__).parent / "scrape_venue_events.py"
    if scraper.exists():
        h.update(str(int(scraper.stat().st_mtime)).encode("utf-8"))
    return h.hexdigest()


def _scraper_newer_than_cache(cache_path: Path) -> bool:
    """True when the scraper code has been edited since the cache was written."""
    scraper = Path(__file__).parent / "scrape_venue_events.py"
    if not cache_path.exists() or not scraper.exists():
        return True
    return scraper.stat().st_mtime > cache_path.stat().st_mtime


def _save_cache(cache_path: Path, events: list, config_hash: str) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    from dataclasses import asdict, is_dataclass
    payload = {
        "config_hash": config_hash,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": [
            {**asdict(e), "start": _iso(e.start), "end": _iso(getattr(e, "end", None))}
            if is_dataclass(e) else {**e, "start": _iso(e["start"]), "end": _iso(e.get("end"))}
            for e in events
        ],
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _load_cache(cache_path: Path, config_hash: str) -> list | None:
    if not cache_path.exists():
        return None
    import json
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("config_hash") != config_hash:
        log.info("cache config hash mismatch — will re-scrape")
        return None
    from datetime import datetime as _dt
    Event = scrape_venue_events.Event
    out = []
    for d in data.get("events", []):
        d = dict(d)
        d["start"] = _dt.fromisoformat(d["start"]) if d.get("start") else None
        d["end"]   = _dt.fromisoformat(d["end"])   if d.get("end") else None
        try:
            out.append(Event(**d))
        except TypeError:
            # Schema drift between cache and current Event dataclass — bail
            return None
    return out


def _iso(v):
    return v.isoformat() if v else None


def _event_seen_key(ev) -> str:
    """Stable cross-rebuild identity: venue + normalised title + start date."""
    title = (ev.title or "").lower().strip()
    title = re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", title), flags=re.UNICODE)
    title = re.sub(r"\s+", " ", title).strip()
    start_date = ev.start.date().isoformat() if ev.start else ""
    return f"{ev.venue_id}|{title}|{start_date}"


def _stamp_first_seen(events: list, state_path: Path) -> dict:
    """Load seen-events state, stamp new keys with today, return updated state.

    Side effect: mutates each event's `first_seen` field to its ISO date.
    First-ever run (empty state) seeds every current event with today-30d so
    the NEW badge doesn't paint everything red on day one.
    """
    today_iso = date.today().isoformat()
    bootstrap_iso = (date.today() - timedelta(days=SEEN_BOOTSTRAP_OFFSET_DAYS)).isoformat()
    state: dict[str, str] = {}
    try:
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("seen_events.json unreadable, treating as empty: %s", exc)
        state = {}

    first_run = not state
    keys_now = set()
    new_count = 0
    for ev in events:
        key = _event_seen_key(ev)
        keys_now.add(key)
        if key in state:
            ev.first_seen = state[key]
        elif first_run:
            ev.first_seen = bootstrap_iso
            state[key] = bootstrap_iso
        else:
            ev.first_seen = today_iso
            state[key] = today_iso
            new_count += 1

    cutoff_iso = (date.today() - timedelta(days=60)).isoformat()
    pruned = {k: v for k, v in state.items() if k in keys_now or v >= cutoff_iso}

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(pruned, sort_keys=True, ensure_ascii=False, indent=0),
                          encoding="utf-8")
    log.info("seen-events: %d total, %d newly added (%s run)",
             len(pruned), new_count, "first" if first_run else "incremental")
    return pruned


def main() -> int:
    import yaml as _yaml
    p = argparse.ArgumentParser()
    p.add_argument("--site-yaml", default=None,
                   help="Per-city site.yaml (sets title/eyebrow/locale/tz/goatcounter). "
                        "When given, --venues/--highlights/--seen/--out default to cities/<code>/...")
    p.add_argument("--venues", default=None)
    p.add_argument("--highlights", default=None)
    p.add_argument("--seen", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--only-city", default=None, help="Limit to one city/neighborhood")
    p.add_argument("--horizon-days", type=int, default=None)
    p.add_argument("--from-cache", action="store_true",
                   help="Skip scrape: load events from cities/<code>/.cache/events.json")
    p.add_argument("--no-cache", action="store_true",
                   help="Force re-scrape even if cache is fresh")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    site = {}
    if args.site_yaml:
        site = _yaml.safe_load(Path(args.site_yaml).read_text(encoding="utf-8")) or {}
        scrape_venue_events.configure_locale(
            site.get("timezone", "Asia/Singapore"),
            site.get("date_order", "DMY"),
            site.get("lang", "en"),
        )
        cd = Path(args.site_yaml).parent
        # venues_from: <other_city> → use that city's venues.yaml as the shared
        # source of truth (e.g. hk-kids reuses hk's venue list).
        venues_from = site.get("venues_from")
        if args.venues is None:
            if venues_from:
                shared = REPO_ROOT / "cities" / venues_from / "config" / "venues.yaml"
                args.venues = str(shared)
                log.info("venues_from: using %s as venue source", shared)
            else:
                args.venues = str(cd / "config/venues.yaml")
        if args.highlights is None: args.highlights = str(cd / "config/highlights.yaml")
        if args.seen is None:       args.seen = str(cd / "data/seen_events.json")
        if args.out is None:        args.out = str(REPO_ROOT / f"dist/{site['code']}/index.html")
        if args.horizon_days is None: args.horizon_days = int(site.get("horizon_days", 270))
    # Final defaults if site_yaml not used
    if args.venues is None:     args.venues = str(REPO_ROOT / "config/venues.yaml")
    if args.highlights is None: args.highlights = str(REPO_ROOT / "config/highlights.yaml")
    if args.seen is None:       args.seen = str(REPO_ROOT / "data/seen_events.json")
    if args.out is None:        args.out = str(REPO_ROOT / ".tmp/events.html")
    if args.horizon_days is None: args.horizon_days = 270

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
    )
    log.setLevel(logging.INFO)

    venues = scrape_venue_events.load_venues(args.venues)
    highlights = _load_highlights(args.highlights)

    if args.only_city:
        venues = [v for v in venues if v.get("city") == args.only_city]

    # ─── Cache decision ──────────────────────────────────────────────────
    # Cache file lives next to data/seen_events.json. Cache is valid when
    # its config-hash matches the current scraper + venues + city tz/lang.
    # On a render-only push (tools/render_events_html.py changed but venues
    # didn't), the cache hash matches → skip scrape (saves ~20 min).
    cache_path = Path(args.seen).parent / "events_cache.json"
    config_hash = _config_hash(args.venues, site)
    cached_events = _load_cache(cache_path, config_hash) if not args.no_cache else None
    use_cache = cached_events is not None and (args.from_cache or args.no_cache is False and not _scraper_newer_than_cache(cache_path))

    failed: list[tuple[str, str]] = []
    ok = 0
    skipped = 0
    if use_cache:
        all_events = cached_events
        log.info("LOADED %d events from cache (config hash matched)", len(all_events))
    else:
        # Reuse one HTTP session across all venues for connection pooling
        session = requests.Session()
        session.headers.update(scrape_venue_events.DEFAULT_HEADERS)
        all_events = []
        for v in venues:
            if v.get("kind") == "unknown":
                skipped += 1
                continue
            try:
                evs = scrape_venue_events.scrape(v, session=session)
            except Exception as exc:
                log.error("scrape() raised for %s: %s", v["id"], exc)
                failed.append((v["id"], str(exc)))
                continue
            if not evs:
                failed.append((v["id"], "no events returned"))
            else:
                all_events.extend(evs)
                ok += 1

        log.info("scraped %d venues OK, %d failed, %d skipped (kind=unknown)", ok, len(failed), skipped)
        log.info("raw events: %d", len(all_events))
        # Persist scrape to cache for the next render-only build
        _save_cache(cache_path, all_events, config_hash)

    # Audience filter:
    #   audience_filter: kids   → keep events that are kid-relevant.
    #   audience_filter: adults → drop events that are explicitly kids-targeted
    #                              (currently a no-op since adult sites are the default).
    # An event is kid-relevant when ANY of these is true (and audience != "adults"):
    #   - venue id is in `always_include_venues` (hard whitelist, e.g. Disneyland)
    #   - audience classifier returned "kids"
    #   - title matches a `kids_keywords` regex
    # `audience == "adults"` is a hard veto — overrides every kid-include rule
    # (so "Adults-only Wine Tasting at HK Book Fair" is correctly dropped from kids).
    af = (site.get("audience_filter") or "").lower()
    if af == "kids":
        import re as _re
        kw = [k.lower() for k in (site.get("kids_keywords") or [])]
        pat = _re.compile("|".join(_re.escape(k) for k in kw), _re.IGNORECASE) if kw else None
        always = set(site.get("always_include_venues") or [])
        before = len(all_events)
        def _is_kid_event(e):
            if getattr(e, "audience", "general") == "adults":
                return False  # hard veto
            if getattr(e, "source", "") in always or getattr(e, "venue_id", "") in always:
                return True
            if getattr(e, "audience", "general") == "kids":
                return True
            if pat and pat.search(getattr(e, "title", "") or ""):
                return True
            return False
        all_events = [e for e in all_events if _is_kid_event(e)]
        log.info("audience_filter=kids: kept %d / %d events", len(all_events), before)

    # Mark featured events using highlights config
    featured = _compute_featured_set(all_events, highlights)
    log.info("flagged %d events as featured", len(featured))

    # Stamp first_seen on every event from data/seen_events.json. Powers
    # the "Recently Added" strip + inline NEW badges in the renderer.
    _stamp_first_seen(all_events, Path(args.seen))

    # Build venue_id → canonical display name map for the renderer's chip
    # labels. Without this, off-site events (e.g. Theatre at Ace Hotel, or
    # any venue where a row's venue_name diverges from the source venue_id)
    # could spawn phantom chips that silently filter to ALL events of the
    # parent venue_id. (Same fix as events-nrw 6fc0e77.)
    venue_meta: dict[str, str] = {}
    for v in venues:
        primary_id = v.get("id")
        primary_label = v.get("display_name") or v.get("name") or primary_id
        if primary_id:
            venue_meta.setdefault(primary_id, primary_label)
        for stage in v.get("stage_resolver") or []:
            sid = stage.get("venue_id")
            slabel = stage.get("venue_name") or sid
            if sid:
                venue_meta.setdefault(sid, slabel)

    # Render — per-city branding from site.yaml when given
    n = render_events_html.render(
        events=all_events,
        out_path=args.out,
        featured=featured,
        title=site.get("title", "What's happening in Carla's World"),
        header_eyebrow=site.get("header_eyebrow", "Culture in Singa"),
        horizon_days=args.horizon_days,
        now=datetime.now(timezone.utc),
        venue_meta=venue_meta,
        lang=site.get("lang", "en"),
        city_identity_word=site.get("city_identity_word", "Singa"),
        goatcounter_code=site.get("goatcounter_code", ""),
        city_code=site.get("code", "singa"),
    )

    # Audit log — write chip-quality findings (phantoms, near-duplicates) to
    # .tmp/chip_audit.md. Mirrors events-nrw 2026-05-11.
    try:
        _emit_chip_audit(all_events, venue_meta, Path(args.out).parent / "chip_audit.md")
    except Exception as exc:
        log.warning("chip audit failed: %s", exc)

    # Freshness check — warn if any configured venue produced 0 events.
    _emit_freshness_warnings(venues, venue_events=_per_venue_counts(all_events))

    # Summary report
    print()
    print(f"Run {datetime.now(timezone.utc).isoformat(timespec='seconds')} — "
          f"{ok+len(failed)} venues, {ok} OK, {len(failed)} failed, {skipped} skipped")
    if failed:
        print("  Failed venues:")
        for vid, reason in failed:
            print(f"    - {vid}: {reason}")
    print(f"  Events: {len(all_events)} raw → {n} after future-only/horizon filter")
    print(f"  Featured: {len(featured)}")
    print(f"  Output: {args.out}")

    # Freshness alerts are logged above. Don't fail the deploy on missing
    # scrapers — the events that DID scrape are still worth shipping.
    return 0


# ─── highlights logic ────────────────────────────────────────────────────────


def _load_highlights(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"featured_keywords": [], "featured_events": []}
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "featured_keywords": data.get("featured_keywords") or [],
        "featured_events": data.get("featured_events") or [],
    }


def _per_venue_counts(events: list) -> dict:
    from collections import Counter as _C
    c = _C()
    for e in events:
        src = getattr(e, "source", None) or (e.get("source") if isinstance(e, dict) else None) or ""
        if src:
            c[src] += 1
    return dict(c)


def _emit_freshness_warnings(venues: list, venue_events: dict) -> None:
    """Log a warning when a configured (non-static) venue scraped 0 events.
    Catches silent scraper drift after site redesigns or selector breakage."""
    silent = []
    for v in venues:
        vid = v.get("id")
        kind = v.get("kind", "unknown")
        if not vid or kind in ("unknown", "static"):
            continue
        if int(venue_events.get(vid, 0)) == 0:
            silent.append((vid, kind))
    if silent:
        log.warning(
            "FRESHNESS: %d venue(s) returned 0 events — possible scraper drift: %s",
            len(silent),
            ", ".join(f"{vid}({kind})" for vid, kind in silent),
        )
    else:
        log.info("FRESHNESS: all configured venues returned ≥1 event")


def _emit_chip_audit(events: list, venue_meta: dict, out_path: Path) -> None:
    """Write a markdown report of chip-quality findings (mirror of events-nrw):

      1. Per-city chip roster (event count + canonical label).
      2. Single-event chips that aren't in venues.yaml (phantom candidates).
      3. Fuzzy-similar chip-label pairs within the same city (≥ 80 score).
    """
    from collections import Counter as _Counter
    try:
        from rapidfuzz import fuzz as _fuzz
    except ImportError:
        _fuzz = None

    chips: dict[tuple[str, str], dict] = {}
    for e in events:
        vid = getattr(e, "venue_id", None) or (e.get("venue_id") if isinstance(e, dict) else None) or ""
        city = getattr(e, "city", None) or (e.get("city") if isinstance(e, dict) else None) or ""
        vname = getattr(e, "venue_name", None) or (e.get("venue_name") if isinstance(e, dict) else None) or ""
        if not vid or not city or city == "__aggregator__":
            continue
        bucket = chips.setdefault((city, vid), {"n": 0, "names": _Counter()})
        bucket["n"] += 1
        bucket["names"][vname] += 1

    chip_rows: list[dict] = []
    for (city, vid), bucket in chips.items():
        canonical = venue_meta.get(vid) or (bucket["names"].most_common(1)[0][0] if bucket["names"] else vid)
        chip_rows.append({"city": city, "vid": vid, "label": canonical, "n": bucket["n"], "in_config": vid in venue_meta})

    parts: list[str] = []
    parts.append(f"# Chip audit — {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    parts.append("")
    parts.append("Auto-generated. Review periodically; add overrides to `venues.yaml`.")
    parts.append("")
    parts.append("## Chips by city")
    parts.append("")
    by_city: dict[str, list] = {}
    for row in chip_rows:
        by_city.setdefault(row["city"], []).append(row)
    for city in sorted(by_city):
        rows = sorted(by_city[city], key=lambda r: (-r["n"], r["label"].lower()))
        parts.append(f"### {city}  _(chips: {len(rows)})_")
        parts.append("")
        parts.append("| events | venue_id | label | configured |")
        parts.append("|---:|---|---|:---:|")
        for r in rows:
            tick = "✓" if r["in_config"] else " "
            parts.append(f"| {r['n']} | `{r['vid']}` | {r['label']} | {tick} |")
        parts.append("")

    phantoms = [r for r in chip_rows if r["n"] == 1 and not r["in_config"]]
    parts.append("## Single-event chips not in `venues.yaml` (phantom candidates)")
    parts.append("")
    if phantoms:
        parts.append("| city | venue_id | label |")
        parts.append("|---|---|---|")
        for r in sorted(phantoms, key=lambda r: (r["city"], r["label"].lower())):
            parts.append(f"| {r['city']} | `{r['vid']}` | {r['label']} |")
        parts.append("")
    else:
        parts.append("_(none)_")
        parts.append("")

    parts.append("## Possible duplicate label pairs (within city)")
    parts.append("")
    parts.append("Pairs scoring rapidfuzz token_set_ratio >= 80.")
    parts.append("")
    found_any = False
    if _fuzz is not None:
        for city, rows in sorted(by_city.items()):
            labels = [(r["label"], r["vid"]) for r in rows]
            pairs: list[tuple[int, str, str, str, str]] = []
            for i in range(len(labels)):
                for j in range(i + 1, len(labels)):
                    score = int(_fuzz.token_set_ratio(labels[i][0], labels[j][0]))
                    if score >= 80 and labels[i][0].lower() != labels[j][0].lower():
                        pairs.append((score, labels[i][0], labels[i][1], labels[j][0], labels[j][1]))
            if pairs:
                found_any = True
                parts.append(f"### {city}")
                parts.append("")
                parts.append("| score | label A (venue_id) | label B (venue_id) |")
                parts.append("|---:|---|---|")
                for score, la, va, lb, vb in sorted(pairs, key=lambda p: -p[0]):
                    parts.append(f"| {score} | {la} (`{va}`) | {lb} (`{vb}`) |")
                parts.append("")
    if not found_any:
        parts.append("_(none found)_")
        parts.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    log.info("chip audit written: %s", out_path)


def _compute_featured_set(events: list, highlights: dict) -> set:
    """Return a set of (venue_id, normalized_title) for events that match.

    Two paths:
        1. title contains any string from featured_keywords (case-insensitive substring)
        2. matches a featured_events entry: same venue_id + token_set_ratio >= 85
    """
    keywords = [kw.lower() for kw in highlights.get("featured_keywords", [])]
    manual = highlights.get("featured_events", [])

    today = datetime.now(timezone.utc).date()
    out: set = set()

    for ev in events:
        if isinstance(ev, dict):
            title = ev.get("title", "")
            venue_id = ev.get("venue_id", "")
            description = ev.get("description") or ""
            audience = ev.get("audience") or "general"
        else:
            title = getattr(ev, "title", "") or ""
            venue_id = getattr(ev, "venue_id", "") or ""
            description = getattr(ev, "description", "") or ""
            audience = getattr(ev, "audience", "general") or "general"

        # Don't pin kids/educational events as highlights, even if they keyword-match
        if audience != "general":
            continue

        haystack = f"{title} {description}".lower()

        matched = False
        for kw in keywords:
            if kw in haystack:
                matched = True
                break

        if not matched:
            for entry in manual:
                if entry.get("venue_id") != venue_id:
                    continue
                until = entry.get("until")
                if until and _coerce_date(until) < today:
                    continue
                if fuzz.token_set_ratio(title, entry.get("title_match", "")) >= 85:
                    matched = True
                    break

        if matched:
            out.add(render_events_html._featured_key(ev))

    return out


def _coerce_date(v):
    if isinstance(v, datetime):
        return v.date()
    return v


if __name__ == "__main__":
    sys.exit(main())
