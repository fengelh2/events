# Project: events

> **Global behavioral rules apply here** (full text in `~/.claude/CLAUDE.md`): (1) **Be brief** — lead with the answer, no preamble or recap. (2) **Verify before you assert** — check facts with a tool this turn instead of guessing, so you rarely need to self-correct; honest corrections stay welcome. (3) **Never mislead, even with true statements** — replace vague reassurance ("fundamentally sound") with specifics, lead with the bad parts, and own any misread your wording caused.

A unified cultural-events calendar covering five real cities (Hong Kong, Hong Kong Kids, Los Angeles, NRW, Singapore, Fukuoka) plus a kids-view sub-calendar over HK. One repo, one deployment, six sub-pages — each rebuilt nightly from its own venue list.

**Live:** https://fengelh2.github.io/events/

## Per-city URLs

| Code | URL | Audience | Venues |
|---|---|---|---|
| `hk` | https://fengelh2.github.io/events/hk/ | Sihan | ~120 |
| `hk-kids` | https://fengelh2.github.io/events/hk-kids/ | Theo (kids view over HK) | (shares HK) |
| `la` | https://fengelh2.github.io/events/la/ | Vicki | ~32 |
| `nrw` | https://fengelh2.github.io/events/nrw/ | Gabi | ~67 |
| `singa` | https://fengelh2.github.io/events/singa/ | Carla | ~58 |
| `fukuoka` | https://fengelh2.github.io/events/fukuoka/ | — | ~20 |

## Architecture

```
events/
├── tools/                              # shared scraper + renderer + orchestrator
│   ├── scrape_venue_events.py          # parametric scraper (15 parser kinds)
│   ├── render_events_html.py           # Apple-agenda HTML + filter panel
│   ├── rebuild_calendar.py             # per-city builder (reads --site-yaml)
│   ├── build_all.py                    # orchestrator: rebuilds all cities into dist/
│   ├── parse_ical.py                   # iCal helper
│   ├── check_links.py                  # post-build link audit
│   ├── investigate_broken_links.py     # broken-link patch suggester
│   └── apply_link_patch.py             # apply patch decisions
├── cities/                             # per-city data
│   ├── hk/      (site.yaml + config/venues.yaml + config/highlights.yaml + data/)
│   ├── hk-kids/ (site.yaml + data/    — venues_from: hk; NO own venues.yaml)
│   ├── la/      (full)
│   ├── nrw/     (full)
│   ├── singa/   (full)
│   └── fukuoka/ (full)
├── dist/                               # built static HTML, deployed to Pages
│   ├── index.html                      # city-picker landing
│   └── {hk,hk-kids,la,nrw,singa,fukuoka}/index.html
└── .github/workflows/rebuild.yml       # daily 20:00 UTC cron + push-trigger
```

## Multi-view cities (hk-kids pattern)

`hk-kids/site.yaml` has `venues_from: hk` — it does NOT carry its own `config/venues.yaml`. The rebuild_calendar loader reuses HK's venue catalog, then applies a kids-specific filter. This lets one scrape pass serve two distinct audiences.

The filter logic (`rebuild_calendar.py` audience filter):
- `audience_filter: kids` → DROP unless the event is kid-relevant
- `audience_filter: adults` → DROP if the event is explicitly kid-only

The two sites configure mirror lists:

| `hk-kids/site.yaml` (admit list) | `hk/site.yaml` (deny list) |
|---|---|
| `always_include_venues` — venues whose programming is overwhelmingly kid/family by default | `kids_only_venues` — same venues, dropped from adult HK |
| `kids_keywords` — title substrings that admit kid programs from mixed venues | `kids_only_keywords` — title substrings that drop kid programs from adult HK |

When adding a new clearly-kid venue, add it to BOTH lists; when adding a new kid keyword pattern, mirror it. Both files have comments showing the pattern.

## Per-city `site.yaml` schema

Required fields (all cities):
```yaml
code:              # subpath in /events/<code>/
name:              # human-friendly city name
flag:              # emoji for landing card
title:             # masthead title
header_eyebrow:    # eyebrow above title
city_identity_word: # word tinted in eyebrow
lang:              # html lang= + dateparser language (en / de / ja)
date_order:        # DMY (HK/SG/NRW), MDY (LA), YMD (fukuoka)
timezone:          # IANA tz; events stored as wall-clock local
horizon_days:      # drop events beyond this future window (default 270)
goatcounter_code:  # subdomain of *.goatcounter.com
```

View-city-only fields (hk-kids):
```yaml
venues_from:       # base-city code to inherit venues from
audience_filter:   # "kids" | "adults"
always_include_venues:  # whitelist (admit any event from these)
kids_keywords:     # admit-by-title-substring list
```

Adult-city-only fields (hk):
```yaml
audience_filter: adults
kids_only_venues:    # mirror of view-city's always_include — drops these
kids_only_keywords:  # mirror of view-city's kids_keywords — drops these
```

## How it builds

`tools/build_all.py` discovers every `cities/*/site.yaml`, then for each city:

1. Subprocesses `rebuild_calendar.py --site-yaml cities/<code>/site.yaml --out dist/<code>/index.html`
2. Calls `scrape_venue_events.configure_locale(tz, date_order, lang)` to reset module globals
3. Loads venues from `cities/<code>/config/venues.yaml` OR `cities/<venues_from>/config/venues.yaml` if `venues_from:` set
4. Iterates every venue, dispatches on `kind:` field
5. Applies audience filter (kids/adults) per site.yaml
6. Filters past + horizon
7. Stamps `first_seen` from `cities/<code>/data/seen_events.json` (powers "NEW" badges)
8. Renders `dist/<code>/index.html`
9. After all cities: writes `dist/index.html` landing page

Each city is a fresh Python subprocess so locale globals stay isolated.

## Supported parser kinds (`kind:` in venues.yaml)

| Kind | Best for |
|---|---|
| `html_list` | Server-rendered card grids — cheapest |
| `detail_pages` | Listing has stable URLs; selectors live on detail page |
| `playwright_html_list` | JS-rendered listings (M+, Tai Kwun, Esplanade…). Supports `use_stealth: true` for Cloudflare. |
| `playwright_detail_pages` | JS-rendered detail pages |
| `ical` | `.ics` exports (HK Chinese Orchestra, The Wanch was) |
| `json_ld_aggregator` | Pages with `<script type="application/ld+json">` Event arrays. Supports `use_playwright: true` + `browser_headers: true` for anti-bot sites (Eventbrite). |
| `tribe_rest` | WordPress + The Events Calendar plugin |
| `flat_json_feed` | Tessitura, LA Phil, Hollywood Bowl |
| `algolia_calendar` | Algolia-backed search (LA Opera) |
| `nextjs_contentful` | Contentful API behind Next.js (Academy Museum) |
| `sistic_api` | SISTIC ticketing CMS — SG ~355 events from one endpoint |
| `et4_search` | et4 tourism portals (visitessen) |
| `toubiz_api` | Toubiz tourism CMS (visitduesseldorf) |
| `static` | Hand-curated `static_events` list |
| `unknown` | Stub — skipped silently. Track these in a future cleanup pass. |

### Anti-bot escalation chain (Eventbrite, Klook, Sassy HK)

For sites that block scraping:

1. `browser_headers: true` — full Chrome fingerprint headers (Sec-Ch-Ua, Sec-Fetch-*). Sometimes enough for header-only sniffing.
2. `use_playwright: true` (on json_ld_aggregator) — real headless Chromium. Defeats TLS fingerprinting. Eventbrite needs this.
3. `use_stealth: true` (on playwright_html_list) — `playwright-stealth` evasions. Defeats Cloudflare. NOT enough for DataDome (Klook).
4. Beyond that — needs residential proxy or paid scraping service. Currently out of scope.

### Per-organizer fallback for Eventbrite

When Eventbrite citywide gets blocked, individual organizer pages (`https://www.eventbrite.com/o/<orgid>`) are less aggressively blocked. Use `kind: detail_pages` against the organizer URL — see `hk-aftermath`, `hk-backstage-comedy`, `hk-seed-by-farmacy` for the pattern.

## Adding a venue

1. Edit `cities/<code>/config/venues.yaml`, add a `- id: …` entry with `kind:` + selectors
2. Validate locally: `python tools/scrape_venue_events.py --venue-id <id> --venues-path cities/<code>/config/venues.yaml`
3. If you want it visible in hk-kids: add to `cities/hk-kids/site.yaml` always_include AND to `cities/hk/site.yaml` kids_only_venues (mirror pair)
4. Commit + push — CI rebuilds + deploys

## Date conventions

- **HK / NRW / SG**: DMY (DD/MM/YYYY)
- **LA**: MDY (MM/DD/YYYY)
- **Fukuoka**: YMD (YYYY/MM/DD)
- All times stored as wall-clock local (no UTC shift)
- `_DATE_PARSER_BASE_SETTINGS.DATE_ORDER` is set per-city by `configure_locale()`
- `_LANGUAGE` is set per-city (German venues silently drop 100% of items if `lang: de` is missing)

## Geographic scope (district chips)

Each city's renderer dynamically builds **Where** chips from event `city` fields:
- **HK / HK Kids**: Hong Kong Island / Kowloon / New Territories
- **LA**: Westside / Central LA / Pasadena & East / Greater LA
- **NRW**: Essen / Düsseldorf / Köln / etc. (free-text from venue addresses)
- **SG**: City Centre / Orchard & Central / East / West & North / Sentosa & South
- **Fukuoka**: Tenjin & Daimyō / Hakata / Momochi / etc.

Aggregators (SISTIC, et4, toubiz, Discover LA, Eventbrite) carry per-event city data and emit sub-venue chips per location.

## CI workflow (`.github/workflows/rebuild.yml`)

- Cron: 20:00 UTC daily (full rebuild)
- Push trigger: scope-detected — only rebuilds cities whose config/site.yaml changed; restores other cities' HTML from gh-pages
- Bot author guard: CI's own `auto: seen_events` commits trigger a FULL rebuild (avoids self-induced scope drift)
- Concurrency: `pages` group, cancel-in-progress: false — sequential builds
- `tools/*.py` change → full rebuild
- `cities/<x>/(config|site.yaml)` change → only `<x>` rebuilds
- `cities/<x>/data/*` change alone → no rebuild trigger

## Analytics

Each city page includes a GoatCounter `<script>`. Unified dashboard: https://fengelh2.github.io/events-stats/

## Gotchas

- **Workspace-root `tools/`** (`c:/Users/asus/Agentic Workflows/tools/`) is **legacy**. Active scraper is `projects/events/tools/`.
- **Eventbrite TLS fingerprinting** — needs `use_playwright: true`. Plain headers (even full Chrome) get 405.
- **Klook / KKday / Sassy AJAX** — DataDome CAPTCHA. Stealth Playwright NOT enough. Static umbrella only.
- **Playwright on Windows** is flaky locally (random EPIPE crashes). Linux CI runner is reliable.
- **SISTIC chip explosion**: the SG SISTIC parser slugifies `venue_name` into sub-venue chips so the renderer shows real venues.
- **`unknown` kind venues** — currently 16 in LA, 22 in NRW. Skipped silently. Track via grep.

## Sister project

[events-stats](https://github.com/fengelh2/events-stats) — unified GoatCounter dashboard.
