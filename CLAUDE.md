# Project: events

A unified cultural-events calendar covering four cities: Hong Kong, Los Angeles, NRW (Essen + Düsseldorf), and Singapore. One repo, one deployment, four sub-pages — each rebuilt nightly from its own venue list.

**Live:** https://fengelh2.github.io/events/

## Per-city URLs

| Code | URL | Audience |
|---|---|---|
| `hk` | https://fengelh2.github.io/events/hk/ | Sihan |
| `la` | https://fengelh2.github.io/events/la/ | Vicki |
| `nrw` | https://fengelh2.github.io/events/nrw/ | Gabi |
| `singa` | https://fengelh2.github.io/events/singa/ | Carla |

## Architecture

```
events/
├── tools/                              # shared scraper + renderer + orchestrator
│   ├── scrape_venue_events.py          # parametric scraper (12+ parser kinds)
│   ├── render_events_html.py           # Apple-agenda HTML + filter panel
│   ├── rebuild_calendar.py             # per-city builder (reads --site-yaml)
│   ├── build_all.py                    # orchestrator: rebuilds all cities into dist/
│   └── parse_ical.py                   # iCal helper
├── cities/                             # per-city data, fully isolated
│   ├── hk/
│   │   ├── site.yaml                   # branding, lang, tz, date_order, GoatCounter
│   │   ├── config/venues.yaml          # ~30 venues
│   │   ├── config/highlights.yaml      # featured-keyword list
│   │   └── data/seen_events.json       # {event_key: first_seen} for "NEW" badges
│   ├── la/   (same shape, ~32 venues)
│   ├── nrw/  (same shape, ~67 venues)
│   └── singa/ (same shape, ~58 venues)
├── dist/                               # built static HTML, deployed to Pages
│   ├── index.html                      # city-picker landing
│   └── {hk,la,nrw,singa}/index.html    # per-city pages
└── .github/workflows/rebuild.yml       # daily 20:00 UTC cron
```

## Per-city `site.yaml` schema

Every city is defined by exactly these fields:

```yaml
code: hk                                # subpath in /events/<code>/
name: Hong Kong                         # human-friendly city name
flag: "🇨🇳"                              # emoji for landing card + switcher
title: "What's happening in Sihan's World"   # masthead title
header_eyebrow: "Culture in Honkers"    # eyebrow above title
city_identity_word: "Honkers"           # word tinted in eyebrow as logo accent
lang: en                                # html lang= + dateparser language
date_order: DMY                         # DMY for HK/SG/NRW, MDY for LA
timezone: Asia/Hong_Kong                # IANA tz; events stored as wall-clock
horizon_days: 270                       # drop events beyond this future window
goatcounter_code: events-hk             # subdomain of *.goatcounter.com
```

## How it builds

`tools/build_all.py` discovers every `cities/*/site.yaml`, then for each city:

1. Subprocesses `rebuild_calendar.py --site-yaml cities/<code>/site.yaml --out dist/<code>/index.html`
2. `rebuild_calendar.py` calls `scrape_venue_events.configure_locale(tz, date_order, lang)` to reset module globals
3. Iterates every venue in `cities/<code>/config/venues.yaml`, dispatches on `kind:` field
4. Filters (drop past events, drop future-beyond-horizon except ongoing exhibitions)
5. Stamps `first_seen` from `cities/<code>/data/seen_events.json` (powers "NEW" badges)
6. Renders `dist/<code>/index.html` with per-city branding + city-switcher top nav
7. After all cities: writes `dist/index.html` landing page

Each city is a fresh Python subprocess so locale globals stay isolated.

## Supported parser kinds (`kind:` in venues.yaml)

| Kind | Best for |
|---|---|
| `html_list` | Server-rendered card grids — cheapest |
| `detail_pages` | Listing has stable URLs; selectors live on detail page |
| `playwright_html_list` | JS-rendered listings (M+, Tai Kwun, Esplanade…) |
| `playwright_detail_pages` | JS-rendered detail pages (HK Palace Museum, Xiqu…) |
| `ical` | `.ics` exports (HK Chinese Orchestra) |
| `json_ld_aggregator` | Sites with `<script type="application/ld+json">` Event arrays (Discover LA) |
| `tribe_rest` | WordPress + The Events Calendar plugin (Pasadena Playhouse, kultur-in-unna) |
| `flat_json_feed` | Tessitura, etc. (LA Phil, Hollywood Bowl) |
| `algolia_calendar` | Algolia-backed search (LA Opera) |
| `nextjs_contentful` | Contentful API behind Next.js (Academy Museum) |
| `sistic_api` | SISTIC ticketing CMS — SG ~355 events from one endpoint |
| `et4_search` | et4 tourism portals (visitessen) |
| `toubiz_api` | Toubiz tourism CMS (visitduesseldorf) |
| `static` | Hand-curated `static_events` list |
| `unknown` | Onboarded but not implemented — skipped silently |

## Adding a venue

1. Edit `cities/<code>/config/venues.yaml`, add a `- id: …` entry with `kind:` + selectors
2. Validate locally: `python tools/scrape_venue_events.py --venue-id <id> --venues-path cities/<code>/config/venues.yaml`
3. Commit + push — CI rebuilds + deploys

## Date conventions

- **HK / NRW / SG**: DMY (DD/MM/YYYY)
- **LA**: MDY (MM/DD/YYYY)
- All times stored as wall-clock local (no UTC shift)
- `_DATE_PARSER_BASE_SETTINGS.DATE_ORDER` is set per-city by `configure_locale()`
- `_LANGUAGE` is set per-city (German dates need `lang: de` to parse "5. Juni 2026")

## Geographic scope (district chips)

Each city's renderer dynamically builds **Where** chips from event `city` fields:
- **HK**: Hong Kong Island / Kowloon / New Territories
- **LA**: Westside / Central LA / Pasadena & East / Greater LA
- **NRW**: Essen / Düsseldorf / Köln / etc. (free-text from venue addresses)
- **SG**: City Centre / Orchard & Central / East / West & North / Sentosa & South

Each event's `city` field drives the chip. Aggregators (SISTIC, et4, toubiz, Discover LA) carry per-event city data and emit sub-venue chips per location.

## Analytics

Each city page includes a GoatCounter `<script>`:
```html
<script data-goatcounter="https://{goatcounter_code}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```
Plus a click-tracker that fires `event-click/<venue>/<title>` whenever a user clicks an event row.

Unified dashboard: https://fengelh2.github.io/events-stats/

## Gotchas

- **Workspace-root tools/** (`c:/Users/asus/Agentic Workflows/tools/`) is **legacy** from the pre-consolidation events-nrw repo. The active scraper is `projects/events/tools/`. Don't edit the workspace-root copy.
- **DATE_ORDER + language** must both be set correctly per-city — German venues silently drop 100% of items if `lang: de` is missing.
- **Discover LA timeout**: this aggregator (487 events) takes >20s. `DEFAULT_TIMEOUT` is 45s — don't lower it.
- **Playwright on Windows** is flaky locally (random EPIPE crashes). Linux CI runner is reliable.
- **SISTIC chip explosion**: the SG SISTIC parser slugifies `venue_name` into sub-venue chips (Esplanade Concert Hall, Victoria Theatre, MBS, etc.) so the renderer shows real venues instead of one "SISTIC" chip.

## Sister project

[events-stats](https://github.com/fengelh2/events-stats) — unified analytics dashboard pulling from each city's GoatCounter site.
