# Project: events

> **Global behavioral rules apply here** (full text in `~/.claude/CLAUDE.md`): (1) **Be brief** — lead with the answer, no preamble or recap. (2) **Verify before you assert** — check facts with a tool this turn instead of guessing, so you rarely need to self-correct; honest corrections stay welcome. (3) **Never mislead, even with true statements** — replace vague reassurance ("fundamentally sound") with specifics, lead with the bad parts, and own any misread your wording caused.

A unified cultural-events calendar covering five real cities (Hong Kong, Hong Kong Kids, Los Angeles, NRW, Singapore, Fukuoka) plus a kids-view sub-calendar over HK. One repo, one deployment, six sub-pages — each rebuilt nightly from its own venue list.

**Live:** https://fengelh2.github.io/events/

## Per-city URLs

| Code | URL | Audience | Venues |
|---|---|---|---|
| `hk` | https://fengelh2.github.io/events/hk/ | Sihan | 122 |
| `hk-kids` | https://fengelh2.github.io/events/hk-kids/ | Theo — **ages 0-5** (kids view over HK) | (shares HK) |

**hk-kids as of 2026-09-10: 244 rows / 209 in the main agenda**, from 40 sources. It was 9 future events on 2026-09-08.
| `la` | https://fengelh2.github.io/events/la/ | Vicki | ~32 |
| `nrw` | https://fengelh2.github.io/events/nrw/ | Gabi | ~67 |
| `singa` | https://fengelh2.github.io/events/singa/ | Carla | ~58 |
| `fukuoka` | https://fengelh2.github.io/events/fukuoka/ | — | ~20 |

## Architecture

```
events/
├── tools/                              # shared scraper + renderer + orchestrator
│   ├── scrape_venue_events.py          # parametric scraper (16 parser kinds)
│   ├── render_events_html.py           # Apple-agenda HTML + filter panel
│   ├── rebuild_calendar.py             # per-city builder (reads --site-yaml)
│   ├── build_all.py                    # orchestrator: rebuilds all cities into dist/
│   ├── parse_ical.py                   # iCal helper
│   ├── zh_gloss.py                     # Chinese title -> rough English gloss
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

**hk-kids targets ages 0-5** (retargeted 2026-09-08). It used to be a broad
0-12 view, which meant 85 U11-U18 ice-hockey fixtures, U10-U14 baseball
tournaments, "ages 13+" ballet masterclasses and HK Phil main-series concerts
(Beethoven 5, Doctor Atomic) dominated a toddler's calendar. The kids filter
therefore runs a **veto layer before every admit rule** — vetoes beat
`always_include_venues`, which admit-only lists could not express:

| Field | Effect |
|---|---|
| `exclude_venues` | venue never admitted, even if whitelisted |
| `veto_keywords` | title substring drops the event outright |
| `max_start_age` | drop when the title STATES a minimum age above this |

`max_start_age` acts only on explicit evidence (`ages 6+`, `U14`, `12-14`,
`8-11yrs`); a title stating no age is untouched, so it never thins the calendar
on a guess. Two asymmetries in `_stated_min_age` are deliberate and were both
found by testing the reject direction:
- Several **explicit** age phrases are constraints on one event → most
  restrictive wins ("ages 13+, 7+ yrs training" → 13).
- Several **U-labels** are the bands on offer → youngest wins ("U6-U18" → 5,
  because a U6 squad does take five-year-olds). Taking the max rejected it.

Keyword matching is word-boundary aware (`_keyword_pattern`), so `child` no
longer matches "Moon*child*'s Dream". Base and plural forms must therefore both
be listed. CJK keywords are deliberately **not** anchored — Python's `\w`
covers CJK, so an anchor would demand a boundary that never occurs inside
Chinese text.

The two sites configure mirror lists:

| `hk-kids/site.yaml` (admit list) | `hk/site.yaml` (deny list) |
|---|---|
| `always_include_venues` — venues whose programming is overwhelmingly kid/family by default | `kids_only_venues` — same venues, dropped from adult HK |
| `kids_keywords` — title substrings that admit kid programs from mixed venues | `kids_only_keywords` — title substrings that drop kid programs from adult HK |

When adding a new clearly-kid venue, add it to BOTH lists; when adding a new kid keyword pattern, mirror it. Both files have comments showing the pattern.

## Where hk-kids' events come from

Added 2026-09-08/09. English-language HK listings are adult city guides; the
toddler content lives in Chinese-language and government sources.

| Source | Kind | What it brings |
|---|---|---|
| `hk-public-libraries-kids` | `html_list` | Cantonese story time across 80+ branches. Biggest single source. |
| `hk-science-museum-kids` | `flat_json_feed` + `inline_json_var` | ~72 future kid workshops. Was returning 0 — its item selector `.content_box` did not exist on the page. |
| `urbtix-lcsd` | `urbtix_xml` | 217 events → 586 dated performances of the government box office. |
| `parentmap-hk` | `html_list` | A dedicated 親子 listings site — whole feed is family. Whitelisted. |
| `art-mate-family` | `html_list` | Arts aggregator, tags 合家歡 + 兒童. Whitelisted (filtered at source). |
| `cityline-hk` | `flat_json_feed` | The entire KidsFest lineup — Gruffalo, Room on the Broom, Stick Man. |
| `asiaworld-expo` | `html_list` | HK's second exhibition hall; home of Ani-Com. |
| `ocean-park-whatson` | `detail_pages` | Rebuilt off sitemap.xml — `/en/whats-on` is a SOFT 404. |

**Eventbrite is blocked from CI** and cannot be fixed by escalation:
`hk-eventbrite-citywide` already runs `use_playwright` + `browser_headers` +
`pages: 25` and returned 0 in CI while fetching fine from a residential IP.
Its `/kids/` and `/children/` category pages hold ~65 good 0-5 events that are
unreachable. **Timable** is deliberately not wired — its `robots.txt` ends
`User-agent: * / Disallow: /`.

## Chinese titles

`tools/zh_gloss.py` turns a Chinese title into a rough English one. The gloss
becomes the row/card HEADLINE and the Chinese original drops to a subtitle,
with a 中文 badge. 47 of 244 rows on the live page.

It is **term substitution, not translation** — word order stays Chinese
("[ every Wed ] PopWalk Summer bumper boats big adventure"). A dictionary was
chosen over a translation API because the nightly build is deterministic and
has no API keys; an API would add per-run cost and a new CI failure mode.

`gloss()` returns None rather than emit a string still >25% CJK, so an
uncovered title keeps its Chinese headline plus the badge instead of becoming
a mangled mix (12 of 244). The original is never discarded — it is what you
search for when booking.

The 中文 badge fires when a source says the event runs in Cantonese/Mandarin
OR when a Chinese title was replaced. There is deliberately **no "EN" badge**:
absence means "not known", and asserting English would invent a fact. A
BILINGUAL title scores no language badge on its own — HK listings are routinely
bilingual and badging them would wrongly warn a non-Chinese-speaking parent off.

**Both renderers need every title change.** `_render_row` and
`_render_featured_card` duplicate this logic. The gloss and the
`__aggregator__` fix each had to be applied twice, and each was noticed only
after the featured strips kept showing the old behaviour.

**Orphaned events (open, 2026-09-08).** The 0-5 retarget added 11 youth-sport
venues to hk-kids' `exclude_venues` while they remain in hk's
`kids_only_venues`, so ~130 events (85 `hkihl-ice-hockey` fixtures, 10
`hk-baseball-youth`, 6 `hk-judo`, …) now render on neither site. Left that way
deliberately: they are U11-U18 league fixtures that suit neither a toddler
calendar nor Sihan's culture calendar. To surface them on adult HK instead,
delete those ids from `hk/site.yaml`'s `kids_only_venues`.

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
# veto layer — all three run BEFORE the admit rules above
exclude_venues:    # venue ids never admitted, even if whitelisted
veto_keywords:     # title substrings that drop the event outright
max_start_age:     # int; drop when the title STATES a min age above this
```

A venue must never appear in both `always_include_venues` and
`exclude_venues`. Adding a venue to `exclude_venues` while it is still listed
in `hk/site.yaml`'s `kids_only_venues` **orphans** it — the events land on
neither calendar. That is currently true of ~130 events, mostly youth-sport
league fixtures; see the mirror-list note below.

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
| `flat_json_feed` | Tessitura, LA Phil, Hollywood Bowl. Also reads a calendar rendered into an inline JS variable via `inline_json_var:` (HK Science Museum) — no Playwright needed. `time_path:` merges a separate "HH:MM" field onto a midnight date; `dedup_key: url_start` keeps recurring sessions that share one detail URL (the default `url` collapses them to a single row). `exclude_field:` + `exclude_values:` DROP matching records — `filter_value` can only include, and Cityline mixes ~35% Shenzhen/Guangzhou/Macau rows into a HK feed. |
| `algolia_calendar` | Algolia-backed search (LA Opera) |
| `nextjs_contentful` | Contentful API behind Next.js (Academy Museum) |
| `sistic_api` | SISTIC ticketing CMS — SG ~355 events from one endpoint |
| `et4_search` | et4 tourism portals (visitessen) |
| `toubiz_api` | Toubiz tourism CMS (visitduesseldorf) |
| `urbtix_xml` | URBTIX / LCSD box office open data (data.gov.hk). Static government XML, no anti-bot. `calendar_url` takes a `{yyyymmdd}` token resolved in Asia/Hong_Kong and retried 2 days back on 404. One Event per `PERFORMANCE` (Charlie and the Chocolate Factory = 31 dates). |
| `static` | Hand-curated `static_events` list. `open_ended: true` marks a permanently-running entry — see the umbrella note below. |
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

### Per-venue date traps (five found, all real)

The city-level `date_order` is a DEFAULT, not a guarantee. HK is DMY, yet five
wired sources print something else. Each needed a per-venue `date_format`:

| Venue | Prints | Fix |
|---|---|---|
| `hk-public-libraries-kids` | `2026/9/12 (Saturday)` — YMD | `date_format: "%Y/%m/%d"` |
| `art-mate-family` | `2026.9.13` — YMD dotted | `date_format: "%Y.%m.%d"` |
| `parentmap-hk` | `2026年8月5日 - 9月13日` | `date_format: "%Y年%m月%d日"` — and `lang: zh` is WORSE, dateparser then reads it as 2026-05-08 |
| `asiaworld-expo` | `06 - 08 Aug 2021` | none needed; fixed in `_parse_date_range` |
| `cityline-hk` / `urbtix-lcsd` | ISO `2027-01-16 23:59` | none — `datetime.fromisoformat` never touches dateparser |

**`_parse_date_range` completes a year-less end of a range in both directions.**
`"06 - 08 Aug 2021"` and `"30 Sep - 01 Oct 2023"` put the year only on the END;
`"2026年8月5日 - 9月13日"` puts it only on the START. Getting this wrong is not a
parse failure — `_parse_one("06")` SUCCEEDS on the bare day and
`PREFER_DATES_FROM: future` rolls it forward, so a 2021 event landed on
2027-09-06 looking entirely plausible. A range spanning New Year is guarded
(`30 Dec - 01 Jan 2024` starts in 2023).

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

## Caching and scrape resilience

**The cache expires.** `CACHE_MAX_AGE_HOURS = 72` in `rebuild_calendar.py`.
Before 2026-09-09 a matching `venue_hash` was a hit forever, and since that
hash covers (venue config + site locale + parser code) — none of which changes
when a venue's own WEBSITE changes — nothing was ever re-fetched. Measured
across 93 nightly runs: all 117 HK venues had byte-identical event arrays and
86% of cached events were already in the past.

Freshness lives in `scraped_at`, which advances ONLY on a real fetch and is
carried forward untouched on a cache hit so age accumulates. **Do not use
`saved_at`** — `_save_cache` rewrites it for every venue every run including
pure cache hits, which is exactly why the staleness was invisible. A block
with no `scraped_at` counts as stale once, so the migration re-scrapes
everything one time.

**Failed scrapes retry once, then fall back — with a bound.**
`_scrape_with_retry` (2 attempts) then `_stale_fallback`, which serves the last
known-good events for at most `EMPTY_FALLBACK_GRACE_DAYS = 7`. The bound is the
point: an unbounded fallback recreates the exact silent rot the max-age exists
to surface. Only a SUCCESSFUL fetch advances `scraped_at`, otherwise a failing
venue would reset its own clock and never age out.

## Renderer: making events reachable

Most of this project's losses have been presentation, not data. Events sat in
the DOM that no user action could reach. Fixed 2026-09-09, all verified in
Chromium:

| Defect | Cost |
|---|---|
| No chip for category `other` | 111 of 174 rows unselectable — the filter bar showed only Exhibition and Sport |
| No chip for `city-aggregator` | 31 rows hidden by ANY Where click and matched by no venue chip |
| No "Later" When slot | rows past next-month had an empty `data-when`, hidden by every When chip — 136 of 513 on HK |
| Featured strips stuck hidden | `syncEmpty()` measured `offsetParent` AFTER setting `display:none`, so a strip never returned; 8 of 19 chips lost all 14 cards until reload |
| Extras toggle unclickable | `.extras-toggle-wrapper { display: none }` hid the only label for 140 `audience-kids`/`audience-active` rows across HK/LA/NRW/SG |
| `__aggregator__` sentinel rendered | leaked into the byline of every aggregator row |

Chips are emitted only when they match ≥1 row and carry their count. The
extras toggle renders only where there is something to reveal.

**`open_ended: true`** (static events) marks a permanently-running entry:
always demoted to the "Ongoing this season" block, visible past its
placeholder end date, and shown as "ongoing" rather than a false countdown.
Without it, 37 rows carrying a placeholder `end: 2026-12-31` behaved like
something CLOSING then — the umbrella demotion switched off once that date came
within 180 days, so 24 sports-class adverts walked to the TOP of the page on
their own, and would have vanished entirely on 2027-01-01.

## Current status (2026-09-10)

**Live:** 244 rows / 209 in the main agenda, 40 sources, 47 English-glossed
Chinese titles. CI runs complete in ~5 minutes.

**Open, in rough value order:**
1. ~47 venues have a `date_extract_regex` with no `date_find_all` and so can
   never emit an `end` — unaudited. See the Gotchas entry.
2. LCSD CLPSS (`/clpss/`) would yield ~389 kid-relevant rows from one request,
   but results are POST-only and no parser kind does POST. A naive empty POST
   returns a 0-byte body; the real form fields are still unknown.
3. 37 collapsed groups fold 140 rows that each had a DISTINCT detail URL, so
   9 of 10 library story-time sessions link to the wrong branch page.
4. ~130 orphaned youth-sport events (see the mirror-list note above).
5. 21 venues found dead or near-dead in the 2026-09-09 audit — `hk-arts-festival`
   (28 items selected, 0 emitted) is the cheapest fix; `tai-kwun` sits behind a
   202 bot challenge.

## Analytics

Each city page includes a GoatCounter `<script>`. Unified dashboard: https://fengelh2.github.io/events-stats/

## Gotchas

- **Workspace-root `tools/`** (`c:/Users/asus/Agentic Workflows/tools/`) is **legacy**. Active scraper is `projects/events/tools/`.
- **Eventbrite TLS fingerprinting** — needs `use_playwright: true`. Plain headers (even full Chrome) get 405.
- **Eventbrite is now blocked in CI outright (2026-09-09).** `hk-eventbrite-citywide` is already fully escalated — `use_playwright: true` + `browser_headers: true` + `pages: 25` — and still returned **0 events** in the 2026-09-08 CI run. It fetches fine (HTTP 200) from a residential IP, so a local test proves nothing: GitHub Actions IP ranges are what Eventbrite blocks. **Do not add more Eventbrite rows** (its `/d/hong-kong-sar/kids/` and `/children/` category pages hold ~65 genuinely good 0-5 events, and are unreachable from CI). Getting them needs a residential proxy or a paid scraping service.
- **Klook / KKday / Sassy AJAX** — DataDome CAPTCHA. Stealth Playwright NOT enough. Static umbrella only.
- **Playwright on Windows** is flaky locally (random EPIPE crashes). Linux CI runner is reliable.
- **SISTIC chip explosion**: the SG SISTIC parser slugifies `venue_name` into sub-venue chips so the renderer shows real venues.
- **`unknown` kind venues** — currently 16 in LA, 22 in NRW. Skipped silently. Track via grep.
- **The scrape cache used to never expire — FIXED 2026-09-09.** All 117 HK venues had byte-identical event arrays across 93 nightly runs. Full detail in **Caching and scrape resilience** above; the short version is that `saved_at` is NOT a freshness signal, `scraped_at` is.
- **A dead venue is usually invisible, and self-declaration doesn't help.** An audit of all 118 HK venues (2026-09-09) found **21 dead** — 11 emitting 0 events, 10 scraping fine but with every event in the past — and **36 of 66 scraped venues produce ≤2 future events**. None of the 21 carried any warning in its `notes`; grepping for "Tier-2 / not pixel-verified" finds only the two already fixed. The real detector is `_emit_drop_warning`, which already fired for 13 of them ("100% dropped", "98% dropped") — it just never ran, because of the cache bug above. With the max-age fix these now surface on their own.
- **A `date_extract_regex` without `date_find_all` can never produce an `end` date.** `_scrape_html_list` uses `re.search` (first match only) unless the venue sets `date_find_all: true`, so a source printing a RANGE collapses to its start. An event whose start is already past then fails the renderer's future-only check and vanishes — even though it is running today. **Fixed and verified: `hk-public-libraries-kids` + `hkpl-events`** (prints a range in 20 of 20 listings; 625 events gained an end date, 213 of them running right now), **`art-mate-family`** (HK Children's Discovery Museum `2023.3.1 - 2026.12.31`, permanently open, was invisible) and **`parentmap-hk`** (all 20 rows). **~47 venues remain in this state, unaudited.** Do not blanket-flip them — check whether the venue's date column ACTUALLY prints ranges first (`the-mills` and `honeycombers-hk` print single dates and were correctly left alone). When adding any venue whose date column shows a range, set `date_find_all: true` and verify the parsed `end`.
- **A veto keyword can cost more than it saves, and only measurement shows it.** Bare `assessment` was added for "school-admission assessment days" — that fired ZERO times, while it killed 12 kid-workshop rows. Bare `roving exhibition` was right 32 of 33 times and killed a Family Fun Day. Vetoes run BEFORE admits, so no `kids_keywords` entry can rescue a wrongly-vetoed row. Before adding a broad veto, grep what it actually matches in the current scrape.
- **Kid-venue coverage WAS thin by construction (largely addressed 2026-09-09).** 25 of the 30 venues whitelisted into hk-kids are `kind: static` — hand-typed umbrella rows ("APSS — Kids Football Classes") that yield 1-6 fixed rows and never change. That, not the filter, is why the 0-5 calendar first looked like a list of sports providers. Real scraped sources have since been added (see "Where hk-kids' events come from"), taking the page from 9 future events to 244 rows. The static rows remain and are fine as venue placeholders — they are now demoted via `open_ended` rather than crowding the top of the page.

## Sister project

[events-stats](https://github.com/fengelh2/events-stats) — unified GoatCounter dashboard.
