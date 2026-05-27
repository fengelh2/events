# Workflow: onboard a new venue

**Trigger:** Adding a new venue, or fixing an existing one whose `kind` is broken.

**Goal:** Find the cheapest viable extraction strategy. Update the venue's row in `cities/<code>/config/venues.yaml` in place. Do NOT create a new file; do NOT write a per-venue scraper.

## Extraction-strategy order (try cheapest first)

1. **iCal (`kind: ical`)** — venue exposes `/?ical=1` or `*.ics`. WordPress Tribe Events plugin commonly does.
2. **JSON-LD aggregator (`kind: json_ld_aggregator`)** — page has `<script type="application/ld+json">` Event blocks. Most modern listing pages.
3. **Server-rendered list (`kind: html_list`)** — repeating card structure with CSS-selectable title + date.
4. **Detail pages (`kind: detail_pages`)** — listing has stable URL patterns; selectors on the detail page.
5. **JavaScript-rendered (`kind: playwright_html_list` or `playwright_detail_pages`)** — last resort. Slower CI.
6. **Specialist parsers** — `tribe_rest`, `sistic_api`, `et4_search`, `toubiz_api`, `algolia_calendar`, `nextjs_contentful`, `flat_json_feed` — use the existing one if the venue runs the same CMS as a sibling.

## Anti-bot escalation

If a site returns 403/405/CAPTCHA:
1. Add `browser_headers: true` (full Chrome fingerprint)
2. If still blocked + it's `json_ld_aggregator`: add `use_playwright: true`
3. If still blocked + it's `playwright_html_list`: add `use_stealth: true`
4. If still blocked → DataDome territory; document why + keep as static umbrella

## Required fields (every venue)

```yaml
- id: city-prefix-slug             # lowercase-hyphen
  name: Full venue name
  display_name: Short label         # optional; defaults to name
  city: <chip value>                # e.g. "Hong Kong Island", or "__aggregator__" for multi-zone
  category: concert|theatre|ballet|opera|film|exhibition|sport|other
  homepage: https://...
  calendar_url: https://...
  kind: <parser kind>
  source_priority: 0|1|2
  # ...kind-specific fields (selectors, regex, etc.)
```

## Test commands

```bash
# Local scrape probe
python tools/scrape_venue_events.py --venue-id <id> --venues-path cities/<code>/config/venues.yaml

# Limit during dev
python tools/scrape_venue_events.py --venue-id <id> --venues-path cities/<code>/config/venues.yaml --limit 5

# Full city rebuild (uses cache where possible)
python tools/rebuild_calendar.py --site-yaml cities/<code>/site.yaml --out /tmp/test.html
```

## For a view-city venue (kid-friendly target in hk-kids)

If the venue should appear in `hk-kids` AND be excluded from adult `hk`:
1. Add the venue to `cities/hk/config/venues.yaml` as normal
2. Add the venue id to `cities/hk-kids/site.yaml` → `always_include_venues:`
3. Add the same id to `cities/hk/site.yaml` → `kids_only_venues:`

The two lists are mirrors and MUST stay in sync.

## Drop-warning behaviour

`_scrape_html_list` warns when >30% of selected items get dropped (typically silent date-parse failure). Override per-venue with `accept_drop_rate: 0.5` if drops are legitimate (closure notices, placeholders). Other parsers currently don't emit this warning — outstanding cleanup item.

## Common gotchas

- **DATE_ORDER** must match the venue's source format. HK/SG/NRW = DMY, LA = MDY, Fukuoka = YMD. Set at city level (`site.yaml`), not per-venue.
- **`lang: de` on NRW** — without it, German dates silently fail 100% of items.
- **Eventbrite** — needs `browser_headers: true` AND `use_playwright: true` AND `pw_wait_ms: 2000`. Plain Chrome UA gets 405 from CI.
- **Discover LA timeout**: 487 events, takes >20s. Don't lower `DEFAULT_TIMEOUT` below 45s.
