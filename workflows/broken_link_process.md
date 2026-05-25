# Broken-link triage process — AUTOMATED

When the link audit flags a URL, the CI pipeline now auto-investigates and
patches the YAML when a working alternative is found.

**No manual investigation needed for URL replacements.** Removals are
informational only — a human still decides whether a venue is truly gone.

## Automated flow (runs on every build)

1. `tools/check_links.py` — HEAD-probes every event URL → `dist/link_audit.json`
2. `tools/investigate_broken_links.py` — for each broken URL:
   - Looks up which YAML entry owns it (venue id, name, city)
   - Probes 15-30 candidates: same-host path variants, alt TLDs (`.hk`, `.com.hk`, etc.) derived from venue name, DuckDuckGo top hits for `"<venue name> <city> official site"`
   - Scores each by: HTTP 200 + body contains a slice of venue name + host matches venue tokens
   - Emits `dist/link_patch.json` with `{patches, removals}`
3. `tools/apply_link_patch.py` — applies the URL→URL swaps to `cities/<code>/config/venues.yaml`; leaves a `.bak` of the original
4. CI commits the patched YAML so future builds use the corrected URL

## Manual fallback (only when auto-investigator can't find anything)

If `dist/link_patch.json.removals` lists an entry, the auto-investigator
exhausted all candidate URLs (paths, TLDs, search) without finding a working
replacement. Then:

## Standard process

For each broken URL:

### 1. Confirm the failure mode

```bash
curl -sIL --max-time 8 "<url>" | head -3
```

- `404 Not Found` → page removed; venue may still exist
- `000 / Could not resolve` → DNS-fail; domain dead
- `403 Forbidden` → bot wall; venue alive, scraper blocked
- `301/302` → moved; follow redirect, update YAML
- `5xx` → temporary; re-check after build cron

### 2. Search for an alternative URL

For each candidate, probe with curl:

```bash
# Try common alternative paths
for p in "" "/en" "/events" "/whats-on" "/calendar" "/programme" "/programmes"; do
  curl -sL --max-time 6 "<root_domain>$p" -o /dev/null -w "%{http_code}\n"
done

# Try alternative subdomains / TLDs
for d in "<name>.com.hk" "<name>.hk" "<name>.co.hk" "www.<name>.org"; do
  curl -sIL --max-time 6 "https://$d/" | head -1
done

# DNS check (sometimes resolver is the problem, not the domain)
nslookup <domain> 8.8.8.8
```

### 3. Cross-check via the venue's social presence

- Facebook page (existence does NOT prove the venue is open)
- Instagram handle (recent posts = open; last post >12mo = likely closed)
- Wikipedia, Google Maps reviews recency

### 4. Decide

| Investigation result | Action |
|---|---|
| Found a working alternative URL | **Update YAML**, push, link audit confirms |
| Domain dead + no social signal of operation | **Remove entry**, push |
| Domain dead but venue confirmed open via social | **Static-events placeholder** with the venue's most stable URL (Wikipedia, Google Maps, Yelp) |
| 403 bot wall, content visible in browser | Add `kind: playwright_html_list`, no removal |
| 5xx transient | Wait for next cron, don't act on first failure |

### 5. Show your work

When making the change, include the investigation in the commit message:

```
fix: Round 1 HK removed (was 404)
- round1.hk / round1.com.hk / round1ent.com/hk → all DNS-fail
- round1usa.com/locations/ static HTML lists no HK store
- FB page exists but no active-business signal
Verdict: no current HK operation.
```

## Hard rule

**Do not auto-exclude in CI.** The link audit is non-fatal by design. Any
exclusion of an entry is a human decision after investigation — not a
silent drop because of a transient 404.
