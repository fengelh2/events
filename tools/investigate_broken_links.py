"""Read dist/link_audit.json, for each broken URL probe candidate alternatives
and print a triage report.

Doesn't auto-edit YAML — surfaces suggestions; human decides per workflow at
projects/events/workflows/broken_link_process.md.
"""
from __future__ import annotations
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

REPO_ROOT = Path(__file__).parent.parent
AUDIT = REPO_ROOT / "dist" / "link_audit.json"
TIMEOUT = 6
UA = "Mozilla/5.0 (compatible; events-investigator/1.0)"
HEADERS = {"User-Agent": UA, "Accept": "*/*"}
COMMON_PATHS = ["", "/", "/en", "/en/", "/events", "/whats-on",
                "/calendar", "/programme", "/programmes", "/whatson"]


def probe(url: str) -> int:
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 405:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, stream=True)
            r.close()
        return r.status_code
    except requests.RequestException:
        return 0


def root_origin(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, "", "", "", ""))


def alt_tlds(host: str) -> list[str]:
    # Strip leading "www."
    h = host[4:] if host.startswith("www.") else host
    base = h.split(".")[0]
    out = []
    for d in (".hk", ".com.hk", ".org.hk", ".com", ".org"):
        if not h.endswith(d):
            out.append(f"https://{base}{d}/")
            out.append(f"https://www.{base}{d}/")
    return out


def investigate(url: str) -> dict:
    origin = root_origin(url)
    parsed = urlparse(url)
    candidates = [origin + p for p in COMMON_PATHS] + alt_tlds(parsed.netloc)
    # Dedupe + cap
    seen, ordered = set(), []
    for u in candidates:
        if u in seen: continue
        seen.add(u); ordered.append(u)
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda u: (u, probe(u)), ordered))
    working = [(u, c) for u, c in results if c in (200, 401, 405)]
    return {"original": url, "origin": origin, "candidates_probed": len(ordered),
            "working_alternatives": working[:6]}


def main():
    if not AUDIT.exists():
        print(f"No audit file at {AUDIT}. Run build_all + check_links first.", file=sys.stderr)
        return 1
    data = json.loads(AUDIT.read_text(encoding="utf-8"))
    sys.stdout.reconfigure(encoding="utf-8")
    for city_code, rep in data.get("cities", {}).items():
        samples = rep.get("samples", [])
        if not samples: continue
        print(f"\n=== {city_code} ({len(samples)} broken sampled) ===")
        for s in samples:
            url = s.get("url")
            print(f"\n  [{s.get('status')}] {url}")
            res = investigate(url)
            if not res["working_alternatives"]:
                print("    no working alternative found via path / TLD probe")
                print("    → manual investigation needed (see workflows/broken_link_process.md)")
            else:
                print("    suggestions:")
                for u, c in res["working_alternatives"]:
                    print(f"      [{c}] {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
