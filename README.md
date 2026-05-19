# events

Unified cultural-events calendar for **Hong Kong**, **Los Angeles**, **NRW** (Essen + Düsseldorf), and **Singapore**. One repo, four sub-pages, rebuilt nightly.

**Live:** https://fengelh2.github.io/events/

| City | URL |
|---|---|
| 🇨🇳 Hong Kong | https://fengelh2.github.io/events/hk/ |
| 🇺🇸 Los Angeles | https://fengelh2.github.io/events/la/ |
| 🇩🇪 NRW | https://fengelh2.github.io/events/nrw/ |
| 🇸🇬 Singapore | https://fengelh2.github.io/events/singa/ |

Each page has a top-bar city switcher to jump between calendars. Filters: **Where** (region) · **What** (category) · **When** (this week / weekend / month / next) · **Venues** (multi-select). Free-text search + favorites + "NEW since last visit" badges. Mobile-first, no JS frameworks.

## Add a venue

```bash
# 1. Edit the per-city venues file
$EDITOR cities/<code>/config/venues.yaml

# 2. Validate locally
python tools/scrape_venue_events.py --venue-id <new-id> --venues-path cities/<code>/config/venues.yaml --limit 5

# 3. Commit + push (CI rebuilds + deploys)
git add cities/<code>/config/venues.yaml && git commit -m "Add <venue>" && git push
```

## Rebuild locally

```bash
# Rebuild one city
python tools/rebuild_calendar.py --site-yaml cities/hk/site.yaml --out /tmp/hk.html --verbose

# Rebuild all four
python tools/build_all.py --verbose
```

## Architecture

See [CLAUDE.md](CLAUDE.md).

## Related

- [events-stats](https://github.com/fengelh2/events-stats) — unified GoatCounter analytics dashboard
