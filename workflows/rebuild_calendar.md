# Workflow: rebuild calendar

**Status:** Full architecture documented in `projects/events/CLAUDE.md`. This file is a thin pointer to current commands.

## Local rebuild

```bash
# One city
python tools/rebuild_calendar.py --site-yaml cities/<code>/site.yaml --out dist/<code>/index.html --verbose

# All cities
python tools/build_all.py --verbose

# Only specific cities
python tools/build_all.py --verbose --only "hk hk-kids"
```

## CI rebuild

- Cron: 20:00 UTC daily (full rebuild) — `.github/workflows/rebuild.yml`
- Push trigger: scope-detected. Only the cities whose `config/` or `site.yaml` changed are rebuilt; others are restored from gh-pages
- Bot author guard: CI's own `auto: seen_events` commits trigger a FULL rebuild
- `tools/*.py` change → full rebuild

## Filter chain (in order)

1. **Scrape** all venues from `cities/<code>/config/venues.yaml` (or `cities/<venues_from>/config/venues.yaml` if `venues_from:` set)
2. **Audience filter** (per `audience_filter:` in site.yaml):
   - `kids` → DROP unless in `always_include_venues`, audience=kids, or title matches `kids_keywords`
   - `adults` → DROP if in `kids_only_venues`, audience=kids, or title matches `kids_only_keywords`
3. **Past filter** — drop events whose start is before today
4. **Horizon filter** — drop events whose start is beyond `horizon_days` (default 270); ongoing exhibitions kept up to +365 days
5. **first_seen stamping** — write `cities/<code>/data/seen_events.json` for "NEW" badges
6. **Render** → `dist/<code>/index.html`

## Related workflows

- `onboard_venue.md` — adding a new venue
- `broken_link_process.md` — link audit + auto-patch pipeline
