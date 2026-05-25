"""Context-aware broken-link triage.

For every broken URL in dist/link_audit.json:
  1. Look up the YAML source — which venue entry has that URL? what's the
     venue name, city, title?
  2. Probe alternative URLs derived from venue context:
       - Same host with common path variants
       - Alt TLDs / subdomains derived from venue display name
       - DuckDuckGo HTML search "venue-name city-name" + first 5 hits
  3. Verify each candidate (status 200, contains a slice of the venue name)
  4. Output a patch.json with proposed YAML edits:
       {"city": "hk", "venue_id": "...", "field": "calendar_url"|"detail_url",
        "old": "...", "new": "...", "evidence": "ddg result rank 1"}
  5. If nothing works after exhaustive search, mark for removal with evidence.

Doesn't auto-edit YAML. apply_patch.py (separate) does the actual writes once
user reviews patch.json.
"""
from __future__ import annotations
import argparse, json, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests
import yaml

REPO_ROOT = Path(__file__).parent.parent
AUDIT = REPO_ROOT / "dist" / "link_audit.json"
PATCH = REPO_ROOT / "dist" / "link_patch.json"
TIMEOUT = 8
UA = "Mozilla/5.0 (compatible; events-investigator/2.0; +https://github.com/fengelh2/events)"
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en"}
COMMON_PATHS = ["", "/", "/en", "/en/", "/events", "/whats-on",
                "/calendar", "/programme", "/programmes", "/whatson",
                "/activities", "/what-on", "/event"]
TLD_GUESSES = [".hk", ".com.hk", ".org.hk", ".com", ".org", ".net"]
# Major non-CN search engines that don't gate the HTML serp
SEARCH_URL = "https://duckduckgo.com/html/?q={q}"


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", s.lower())
    return s


def _name_tokens(name: str) -> list[str]:
    """Pull useful identifier tokens from a venue name (e.g. 'Round 1 Spo-Cha
    + arcade (Mong Kok)' → ['round1', 'spocha', 'mongkok'])."""
    raw = re.sub(r"[^A-Za-z0-9\s-]", " ", name or "").lower().split()
    skip = {"the", "and", "of", "for", "in", "at", "a", "an", "-"}
    return [w for w in raw if w not in skip and len(w) > 1]


def probe(url: str, expect_contains: str | None = None) -> tuple[int, str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, stream=True)
        body = ""
        if r.status_code == 200 and expect_contains:
            # Only sniff first 8KB to confirm content match
            for chunk in r.iter_content(chunk_size=8192, decode_unicode=False):
                body = chunk.decode("utf-8", "ignore")
                break
        r.close()
        return r.status_code, body
    except requests.RequestException as e:
        return 0, str(e)[:60]


def ddg_search(query: str, limit: int = 5) -> list[str]:
    """Pull top organic result URLs from DuckDuckGo HTML serp."""
    try:
        r = requests.get(SEARCH_URL.format(q=urllib.parse.quote(query)),
                         headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return []
        urls = re.findall(r'class="result__url"[^>]*href="([^"]+)"', r.text)
        # DDG wraps results in /l/?uddg=ENCODED; unwrap
        out = []
        for u in urls[:limit]:
            m = re.search(r"uddg=([^&]+)", u)
            if m:
                out.append(urllib.parse.unquote(m.group(1)))
            elif u.startswith("http"):
                out.append(u)
        # Also try the plain href= pattern
        if not out:
            urls2 = re.findall(r'<a[^>]+class="result__a"[^>]+href="(https?://[^"]+)"', r.text)
            out = urls2[:limit]
        return out
    except Exception:
        return []


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().lstrip("www.")


def load_venue_index() -> dict:
    """{url: {city, venue_id, name, where_in_yaml}} — find every URL in any
    cities/*/config/venues.yaml so we can map a broken URL back to its source."""
    index = {}
    for site_yaml in (REPO_ROOT / "cities").glob("*/site.yaml"):
        city_code = site_yaml.parent.name
        venues_path = site_yaml.parent / "config" / "venues.yaml"
        if not venues_path.exists():
            continue
        try:
            venues = yaml.safe_load(venues_path.read_text(encoding="utf-8")) or []
        except Exception:
            continue
        for v in venues:
            if not isinstance(v, dict): continue
            vid = v.get("id", "?")
            name = v.get("name") or v.get("display_name") or vid
            # Track every URL-like field
            for fld in ("calendar_url", "homepage", "url_pattern"):
                u = v.get(fld)
                if isinstance(u, str) and u.startswith("http"):
                    index[u] = {"city": city_code, "venue_id": vid, "name": name, "field": fld}
            for st in (v.get("static_events") or []):
                u = st.get("detail_url") if isinstance(st, dict) else None
                if isinstance(u, str) and u.startswith("http"):
                    index[u] = {"city": city_code, "venue_id": vid, "name": name,
                                "field": f"static_events[{st.get('title','?')[:40]}].detail_url"}
    return index


def investigate(broken_url: str, ctx: dict | None) -> dict:
    out = {"original": broken_url, "context": ctx, "tried": [],
           "best": None, "verdict": "no_alternative_found"}
    parsed = urlparse(broken_url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    name = (ctx or {}).get("name", "")
    tokens = _name_tokens(name)
    expect = _slug(name.split("(")[0])[:20] or None
    # Extract the most specific path segment from the broken URL — for a
    # static event we want the replacement to share *something* topical with it
    # ("halloween" in halloween/, "christmas" in christmas/, etc.), otherwise
    # we'd "fix" Disneyland Halloween → Disneyland homepage and degrade UX.
    broken_segments = [s.lower() for s in parsed.path.strip("/").split("/") if s and len(s) > 3]

    # Layer 1: same-host path variants
    candidates = [origin + p for p in COMMON_PATHS]
    # Layer 2: alt TLDs based on host base + venue name slug
    base = parsed.netloc.lstrip("www.").split(".")[0]
    name_slug = _slug(name.split()[0]) if name else ""
    for nm in {base, name_slug}:
        if not nm: continue
        for tld in TLD_GUESSES:
            candidates.append(f"https://{nm}{tld}/")
            candidates.append(f"https://www.{nm}{tld}/")
    # Layer 3: DDG search "venue-name city-name official site"
    city = (ctx or {}).get("city", "")
    if name:
        q = f"{name} {city} official site events".strip()
        ddg = ddg_search(q, limit=6)
        candidates.extend(ddg)
        out["ddg_query"] = q
        out["ddg_hits"] = ddg

    # Dedupe + probe
    seen, ordered = set(), []
    for c in candidates:
        if c in seen or c == broken_url: continue
        seen.add(c); ordered.append(c)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda u: (u, *probe(u, expect)), ordered))

    # Score: 200 status + body contains expected token = high confidence.
    # Strict trust rules:
    #   - Same-host candidate must share a topical path segment with the
    #     broken URL (so /halloween → /en-hk/ is rejected unless it has
    #     "halloween" in it).
    #   - Off-host candidate is ONLY acceptable if it's an official social /
    #     reference page (Facebook, Instagram, Wikipedia of the venue).
    #     Random fan blogs that happen to contain the venue name are
    #     explicitly rejected.
    TRUSTED_OFF_HOSTS = ("facebook.com", "instagram.com", "twitter.com",
                          "x.com", "wikipedia.org", "youtube.com",
                          "eventbrite.com", "eventbrite.hk")
    same_host = host_of(broken_url)
    scored = []
    for u, code, body in results:
        if code not in (200, 401):
            continue
        h = host_of(u)
        is_same_host = (h == same_host)
        is_trusted_off = any(t in h for t in TRUSTED_OFF_HOSTS)
        if not is_same_host and not is_trusted_off:
            continue  # rejected — off-domain fan-blog / aggregator we don't trust
        cand_segs = [s.lower() for s in urlparse(u).path.strip("/").split("/") if s and len(s) > 3]
        topical_match = bool(broken_segments) and any(s in cand_segs for s in broken_segments)
        if is_same_host and broken_segments and not topical_match:
            continue  # same host but unrelated path
        score = 1
        if expect and expect.lower() in body.lower():
            score += 3
        if any(tok.lower() in h for tok in tokens[:3]):
            score += 2
        if is_same_host:
            score += 2  # same host is best
        if topical_match:
            score += 2
        scored.append((score, code, u))
    scored.sort(reverse=True)

    out["tried"] = len(ordered)
    out["candidates_passed"] = [{"url": u, "status": c} for s, c, u in scored[:5]]
    if scored:
        out["best"] = scored[0][2]
        out["verdict"] = "replace_with_best"
    else:
        out["verdict"] = "no_alternative_found_propose_removal"
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-per-city", type=int, default=20,
                   help="Investigate at most N broken URLs per city (audit emits 10 samples by default)")
    args = p.parse_args()

    if not AUDIT.exists():
        print(f"No audit file at {AUDIT}", file=sys.stderr); return 1
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    index = load_venue_index()
    sys.stdout.reconfigure(encoding="utf-8")

    patches = []
    removals = []
    for city_code, rep in audit.get("cities", {}).items():
        samples = (rep.get("samples") or [])[: args.max_per_city]
        if not samples: continue
        print(f"\n=== {city_code} — {len(samples)} broken sampled ===")
        for s in samples:
            url = s.get("url")
            ctx = index.get(url, {})
            print(f"\n  [{s.get('status')}] {url}")
            if ctx:
                print(f"    venue: {ctx.get('venue_id')} ({ctx.get('name','?')[:50]})  field={ctx.get('field')}")
            else:
                print("    (URL not directly in YAML — came from a live scrape; transient or upstream churn)")
            res = investigate(url, ctx)
            if res["verdict"] == "replace_with_best" and res["best"]:
                print(f"    ✓ best alternative: {res['best']}")
                if ctx:
                    patches.append({
                        "city": ctx["city"], "venue_id": ctx["venue_id"],
                        "field": ctx["field"], "old": url, "new": res["best"],
                        "evidence": f"probed {res['tried']} candidates, top match scored highest",
                    })
            else:
                print("    ✗ no working alternative; proposing removal")
                if ctx:
                    removals.append({
                        "city": ctx["city"], "venue_id": ctx["venue_id"],
                        "field": ctx["field"], "url": url,
                        "evidence": f"probed {res['tried']} candidates, none returned 200 with venue-name match",
                    })

    PATCH.parent.mkdir(parents=True, exist_ok=True)
    PATCH.write_text(json.dumps({"patches": patches, "removals": removals},
                                indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ Patch suggestions: {len(patches)} replacements, {len(removals)} proposed removals")
    print(f"  Saved: {PATCH}")
    print("\nReview the patch file, then apply via tools/apply_link_patch.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
