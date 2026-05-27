# Spring Clean Findings (2026-05-28)

Output from 4 parallel audit agents (cross-city consistency, scraper code quality, build pipeline, docs+workflows). Findings split by what was already applied vs what's queued for user review.

---

## ✅ Already applied (commits 3baa942, 9809cff)

| Severity | Item | Commit |
|---|---|---|
| P0 | CI scope-detect was rebuilding only 1 city when CI's own `auto: seen_events` commits landed → others stayed stale on gh-pages. Now ignores `data/` paths AND skips scope when actor is `github-actions[bot]`. | 3baa942 |
| P0 | `build_all` returned `0` always → CI never went red on total failure. Now returns 1 if all cities failed. | 3baa942 |
| P0 | `hk-kids` always_include referenced non-existent venue `hk-science-museum` (real id is `hk-science-museum-kids`). | 3baa942 |
| P0 | Stale `cities/hk/config/venues.yaml.bak` checked in. Deleted. | 3baa942 |
| P1 | `eventbrite-sg` + `-p2` + `-p3` missing the `use_playwright`/`browser_headers` flags HK got — Singapore was getting 405 from CI. | 3baa942 |
| P1 | `investigate_broken_links.host_of()` and TLD-fallback used `lstrip("www.")` which strips characters not prefix (`"www2.x"` → `"2.x"`). | 3baa942 |
| P1 | `apply_link_patch` used `text.replace(old, new)` (replace-all) — would collateral-replace if same URL appeared in multiple venue blocks. Now `replace(old, new, 1)`. | 3baa942 |
| P2 | Duplicate imports: `import html as _html` at L2843 and `import json as _json` at L1636 — both already module-level. | 9809cff |
| Docs | `CLAUDE.md` was 4-city; rewrote to 6, added `hk-kids` architecture, audience-filter mirror pattern, anti-bot escalation chain, current parser kinds. | 3baa942 |
| Docs | `workflows/rebuild_calendar.md` was entirely pre-consolidation NRW-era fiction — replaced with a thin pointer to CLAUDE.md. | 3baa942 |
| Docs | `workflows/onboard_venue.md` updated paths (events-nrw → events/cities/<code>), added anti-bot escalation, view-city onboarding pattern. | 3baa942 |
| Docs | `README.md` 6-city table. | 3baa942 |

---

## 🟡 In progress (background agent)

- Scraper DRY pass: `_dismiss_cookies` helper, `_emit_drop_warning` helper called from every parser (closes a long-standing silent-drop blind spot), `_UA_WINDOWS_CHROME` module constant (currently 3 different Chrome versions hardcoded). Will report back with test-verified outcome.

---

## 🔴 Queued for your review (not applied)

### Build pipeline

| # | Severity | Item | File:line |
|---|---|---|---|
| 1 | P1 | `_attr(ev,"url")` is rendered into `href="{url}"` after `html.escape` — but escape doesn't reject `javascript:` schemes. **XSS surface** if any scraper ever returns a `javascript:` URL. Fix: reject any URL not starting with `http://` / `https://` / `/` / `#`. | render_events_html.py:1148,1247 |
| 2 | P1 | `check_links.py` no per-host concurrency cap → 20 workers can saturate one slow host (Esplanade) and time-out everything. | check_links.py |
| 3 | P1 | `check_links.py` no retry on transient `ConnectionError`/`ReadTimeout` → one blip marks URL broken → investigator may auto-replace a perfectly fine URL with a guess. | check_links.py |
| 4 | P1 | Eventbrite organizer URLs are auto-trusted in patcher → a malicious page matching the venue slug could be proposed as a patch. Fix: require path-token match for trusted-off-host candidates too. | investigate_broken_links.py:181-205 |
| 5 | P1 | rebuild_calendar audience comparison `e.audience == "adults"` is case-sensitive — if any scraper ever returns `"Adults"` the hard veto silently fails. | rebuild_calendar.py:284 |
| 6 | P2 | seen-events bootstrap (`first_run = not state`) triggers on EMPTY dict too — if `seen_events.json` ever gets corrupted to `{}` mid-life, every event re-stamps and the NEW badge re-fires for everything. Fix: guard on file absence specifically. | rebuild_calendar.py:143 |
| 7 | P2 | Long-running "ongoing" events with `end = 2099-12-31` would pass forever and never age out. | render_events_html.py:413-423 |
| 8 | P2 | iCal events with `T000000` start (true midnight concerts) get mislabelled "all day". | render_events_html.py:1207 |

### Cross-city consistency

| # | Severity | Item |
|---|---|---|
| 9 | P1 | **LA has 16/32 `kind: unknown` venues** (norton-simon, geffen-playhouse, the-broad, moca, etc.) — silently skipped by dispatcher. LA is half-stubbed. Either implement parsers or convert to `kind: static` with empty list to make stub status explicit. |
| 10 | P1 | **NRW has 22/67 `kind: unknown`** venues (mostly Düsseldorf galleries + Ruhr venues). Same triage needed. |
| 11 | P2 | Category vocabulary divergence: fukuoka has BOTH `film` AND `cinema`; singa adds `art`/`vernissage`; nrw adds `vernissage`. Should be canonicalised and collapsed. |
| 12 | P2 | All 6 cities use identical `goatcounter_code: fengelh` — either each city should have a unique one, or hoist to project-level constant. |
| 13 | P2 | LA `new-beverly` has unique `date_prefer: current_period` field — verify it's actually consumed, drop if dead. |

### Scraper code quality (deferred — high-risk refactor)

| # | Severity | Item | Est. LOC |
|---|---|---|---|
| 14 | P1 | `_make_event(venue_row, title, start, end, url, category, **overrides)` factory — currently 12 sites repeat the same trailing `Event(...)` field block. Saves ~80 LOC. Risky — touches every parser. | -80 |
| 15 | P1 | `_assemble_from_detail_soup()` helper — nearly identical 50-line detail-extraction loop in `_scrape_detail_pages` (L197-245) and `_scrape_playwright_detail_pages` (L585-643). | -50 |
| 16 | P1 | `_pw_session(use_stealth, viewport, locale, ua)` context-mgr — Playwright launch + context + UA block duplicated 4x with diverging UAs and viewports. | -50 |
| 17 | P1 | `_display(venue_row)` helper — `venue_row.get("display_name") or venue_row["name"]` repeats ~20x. | -15 |
| 18 | P1 | `_normalize_base_category()` — `"mixed" → "other"` repeated 8x. | -14 |
| 19 | P2 | 11+ bare `except Exception:` clauses in Playwright code — should narrow to `PlaywrightTimeoutError` / `RequestException`. |  |
| 20 | P2 | `_DATE_PARSER_BASE_SETTINGS` redeclared at L2272 — brittle. Initialise once at module load. | -6 |
| 21 | P2 | `_HK_TZ = _LOCAL_TZ` back-compat alias used in ~15 places — misleading for LA/NRW/SG. Rename to `_LOCAL_TZ` throughout. |  |
| 22 | P3 | Regex-based `<script type="application/ld+json">` parsing on aggregator pages (L905) — fragile vs nested HTML edge cases. Should use BS4. |  |
| 23 | P3 | Magic numbers without constants: `max_details=60`, `max_details=30`, `max_pages=30`/`25`/`20`, scroll iterations `range(8)`/`range(6)`. |  |

### Docs

| # | Severity | Item |
|---|---|---|
| 24 | P2 | LA `audience_filter: adults` on hk site.yaml — the value is documentation only; filter logic is driven by `kids_only_*` lists. Either wire it up or drop the field. |
| 25 | P2 | "Adding a venue" exists in CLAUDE.md, README.md, AND workflows/onboard_venue.md — three slightly different versions. Consolidate. |

---

## Suggested next moves

**Quick wins** (15-30 min, low risk):
- #1 (XSS guard in render)
- #5 (case-insensitive audience comparison)
- #20 (one-shot DATE_PARSER_BASE_SETTINGS init)
- #21 (rename `_HK_TZ` → `_LOCAL_TZ`)

**Medium** (~1-2 hr, needs testing):
- #14, #15, #16, #17, #18 (DRY pass — see in-progress agent)
- #9, #10 (triage `unknown` venues — biggest impact: LA's 16 venues are real institutions silently dropped)
- #3 (retry transient errors)

**Larger projects**:
- #4 (link audit trust hardening — needs design pass)
- #11 (canonical category vocabulary across cities)
