"""Audit event-detail links in built dist/<city>/index.html files.

Probes each unique <a href> with a HEAD request (falls back to GET on 405)
in parallel. Reports broken URLs grouped by city + host, writes JSON.

Run after build_all.py. Doesn't fail the build — just records.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import Counter, defaultdict
from urllib.parse import urlparse

import requests

REPO_ROOT = Path(__file__).parent.parent
DIST = REPO_ROOT / "dist"
TIMEOUT = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; events-link-checker/1.0; +https://github.com/fengelh2/events)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en,de;q=0.5",
}
# Status codes treated as "OK" — 200 obviously, but also redirects (3xx) since
# we follow them, and 401/405 (page exists but blocked HEAD).
OK_CODES = {200, 401, 405}
# Hosts we know bot-wall HEAD requests — treat any 403 as OK for these.
BOT_WALL_HOSTS = {
    "asiasociety.org", "www.westk.hk",
    "www.timeout.com", "www.honeycombers.com",
}


def extract_links(html: str) -> set[str]:
    """Pull every event-link href. Skip in-page anchors + the city switcher."""
    links = set()
    for m in re.finditer(r'<a\s+class="(?:row|featured-card)[^"]*"\s+href="([^"]+)"', html):
        url = m.group(1).strip()
        # Decode HTML entities the renderer escaped (e.g. &amp;)
        url = url.replace("&amp;", "&").replace("&#x27;", "'").replace("&quot;", '"')
        if url.startswith(("http://", "https://")):
            links.add(url)
    return links


def probe(url: str) -> tuple[str, int, str]:
    host = urlparse(url).netloc.lower()
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        code = r.status_code
        if code == 405:  # method not allowed → retry GET
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, stream=True)
            code = r.status_code
            r.close()
    except requests.RequestException as exc:
        return url, 0, str(exc)[:60]

    if code in OK_CODES:
        return url, code, "ok"
    if code == 403 and host in BOT_WALL_HOSTS:
        return url, code, "ok-botwall"
    return url, code, "fail"


def audit_city(code: str, html_path: Path, workers: int = 20) -> dict:
    html = html_path.read_text(encoding="utf-8")
    links = extract_links(html)
    total = len(links)
    if total == 0:
        return {"city": code, "total": 0, "broken": 0, "broken_by_host": {}, "samples": []}

    results: list[tuple[str, int, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(probe, u): u for u in links}
        for f in as_completed(futures):
            results.append(f.result())

    broken = [(u, c, s) for u, c, s in results if s == "fail"]
    by_host: Counter = Counter()
    for u, c, _ in broken:
        by_host[urlparse(u).netloc.lower()] += 1

    return {
        "city": code,
        "total": total,
        "broken": len(broken),
        "broken_pct": round(100 * len(broken) / total, 1) if total else 0,
        "broken_by_host": dict(by_host.most_common(15)),
        "samples": [{"url": u, "status": c} for u, c, _ in broken[:10]],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cities", nargs="*", default=["hk", "la", "nrw", "singa"])
    p.add_argument("--out", default=str(DIST / "link_audit.json"))
    p.add_argument("--workers", type=int, default=20)
    args = p.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    started = time.time()
    out = {"audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cities": {}}
    grand_total = grand_broken = 0
    for code in args.cities:
        html_path = DIST / code / "index.html"
        if not html_path.exists():
            print(f"  {code}: SKIP (no dist/{code}/index.html)")
            continue
        rep = audit_city(code, html_path, workers=args.workers)
        out["cities"][code] = rep
        grand_total += rep["total"]
        grand_broken += rep["broken"]
        print(f"  {code:>6}: {rep['broken']:>4} / {rep['total']:<5} broken ({rep['broken_pct']}%)"
              f"  top hosts: {dict(list(rep['broken_by_host'].items())[:3])}")
    out["grand_total"] = grand_total
    out["grand_broken"] = grand_broken
    out["grand_pct"] = round(100 * grand_broken / grand_total, 1) if grand_total else 0
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    elapsed = time.time() - started
    print(f"\nTotal: {grand_broken}/{grand_total} broken ({out['grand_pct']}%)  [{elapsed:.0f}s]")
    print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
