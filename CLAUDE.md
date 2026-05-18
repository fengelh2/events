# Project: events-singa

A weekly cultural-events calendar covering Singapore. Aggregates upcoming events from major museums, opera, ballet, classical concerts, theatre, plus Chinese opera + Malay/Indian/Peranakan performance traditions.

Sister project of [events-nrw](https://github.com/fengelh2/events-nrw) (German, Essen + Düsseldorf) and [events-la](https://github.com/fengelh2/events-la) (English, Los Angeles). Codebases are independent so improvements don't ripple between locales — port intentionally when the logic is generic.

## Goal

A simple, easy-to-read web page rebuilt nightly that lists upcoming cultural events. Filters: **Where** (region) · **What** (category) · **When** (this week / weekend / month / next) · **Venues** (multi-select, click to add). Free-text search + favorites + "NEW since last visit" badges via localStorage. Mobile-first, no JS frameworks, deploys to GitHub Pages.

## Inputs

- `config/venues.yaml` — venue master list.
- `config/highlights.yaml` — featured-keyword list (HK-relevant: artists, composers, blockbuster productions).

## Outputs

- `.tmp/events.html` — single static page, rebuilt nightly. Deployed to `gh-pages` by GitHub Actions; served at `https://<user>.github.io/events-singa/`.

## Language policy

- **UI: English.** All headings, labels, dates, filter chips.
- **Event titles + descriptions: as-is from source.** If a venue publishes Chinese-only programmes (e.g. Sunbeam Theatre Cantonese opera), the title stays in Chinese — do NOT translate.
- **Prefer the English toggle** of bilingual sites (most HK cultural sites have one). Use the Chinese version only when no English exists.

## Canonical Event schema

```yaml
title: str            # English or Chinese, as published
start: datetime       # ISO 8601, with timezone (Asia/Singapore)
end: datetime | null
venue_id: str
venue_name: str
city: str             # 'Singapore' (single zone — HK is MTR-compact)
category: str         # museum_exhibition | opera | ballet | concert | theatre | film | vernissage | other
url: str
description: str | null
audience: str         # general | educational | active | kids
```

## Date conventions

- HK uses **DMY** (DD/MM/YYYY) — same as the UK and events-nrw. Set in `_DATE_PARSER_BASE_SETTINGS` as `DATE_ORDER='DMY'`.
- All event times are `Asia/Singapore` (UTC+8, no DST). Times stored as wall-clock local — never UTC.
- Display: 12-hour clock with AM/PM ("7:30 PM"), date as "Sunday, 10 May".

## Geographic scope

**Single zone: "Singapore".** HK is compact and MTR-connected (~45 min venue-to-venue), so district-splitting adds friction without value. If later useful, an optional `region` free-text field (Singapore Island / Kowloon / New Territories) can drive secondary filters.

## Scrape landscape (per HK reconnaissance, 2026-05-17)

- **Bot walls are the dominant pattern.** M+, Tai Kwun, West Kowloon (westk.hk), HK Palace Museum, Asia Society all 403 unauthenticated requests. Plan for `playwright_html_list` + realistic User-Agent + Accept-Language headers on modern museum/cultural sites.
- **LCSD aggregator covers 7+ venues** via one parser: HK Cultural Centre, City Hall, Sha Tin Town Hall, Kwai Tsing Theatre, Tsuen Wan Town Hall, Yuen Long Theatre, Tuen Mun Town Hall. Biggest single ROI.
- **HK Chinese Orchestra exposes per-event .ics** ("Add to Outlook") — clean iCal source.
- **HK Phil server-renders** a tabular concert list — straightforward html_list.
- **URBTIX is the ticketing hub** — transaction layer, not a calendar; don't try to parse it for metadata.
- **Season-shaped sites** (HK Ballet, Opera HK, HK Arts Festival): expect 0 events for months, then a burst. Gate freshness alerts with slow-decay (60+ days).
- **Cantonese opera (Sunbeam, xiqu troupes)** is Chinese-only by tradition. Accept Chinese titles.

## Onboarding order (Tier-1)

1. **LCSD performing-arts e-Calendar** — `https://www.performing-arts.gov.hk/en/e-calendar.html`. One parser, 7+ venues.
2. **HK Phil** — `https://www.hkphil.org/concert`. ~80 concerts, server-rendered.
3. **HK Chinese Orchestra** — `https://www.hkco.org/en/Concerts-Activities/Upcoming-Concerts.html`. Per-event .ics available.
4. **HK Museum of Art** — `https://hk.art.museum/en/web/ma/exhibitions-and-events.html`. Server-rendered, cleanest of the museums.

Then (Tier-2, needs Playwright): M+, Tai Kwun, West Kowloon Xiqu Centre, HK Palace Museum.

## Gotchas / non-obvious notes

- **No JSON-LD on HK sites.** Reconnaissance found zero `@type: Event` blocks. Don't grep for it.
- **LCSD URL migration in progress.** Old `lcsd.gov.hk/en/{venue}/programmes/currentmonth.html` URLs 302-redirect to `performing-arts.gov.hk` — follow redirects.
- **HKAPA volume needs filtering.** ~190 paginated pages including student recitals + room hirers; filter to `Academy Production` categories or you'll drown the calendar.
- **Time zone matters.** All event times are `Asia/Singapore`. Don't UTC-shift.
- **Don't translate.** Mum / user reads Chinese fine; leave Cantonese-opera and other Chinese-only titles untouched.
