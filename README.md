# events-singa

Cultural events calendar for Singapore — museums, opera, ballet, classical concerts, theatre, Chinese opera + Malay/Indian/Peranakan performance traditions.

**Live page:** https://fengelh2.github.io/events-singa/

Auto-rebuilds nightly via GitHub Actions. State (favorites, "new since last visit" badges) lives in browser localStorage; no backend.

Sister projects:
- [momevents](https://github.com/fengelh2/events-nrw) — German cultural calendar (Essen + Düsseldorf)
- [events-la](https://github.com/fengelh2/events-la) — English, Los Angeles

Codebases are independent so improvements don't ripple between locales — port intentionally when the logic is generic.

## Local development

```sh
pip install -r requirements.txt
python tools/rebuild_calendar.py --verbose
```

Output: `.tmp/events.html`. Serve locally:

```sh
cd .tmp && python -m http.server 18082
# then open http://localhost:18082/events.html
```

## Architecture

The scraper is a parametric layer over per-venue config in `config/venues.yaml`. Each venue declares `kind: ical | html_list | playwright_html_list | static` plus selectors / regex helpers. See [CLAUDE.md](CLAUDE.md) for goals, gotchas, scrape landscape.

Tier-1 onboarding starts with the **LCSD Performing Arts e-Calendar** (covers 7+ government venues at once), then HK Phil, HK Chinese Orchestra, HK Museum of Art.
