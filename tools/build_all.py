"""Build all cities into dist/.

Runs each city's rebuild in a separate Python subprocess so the locale
configuration (timezone, date_order) stays isolated. Writes:
  dist/index.html           — landing page (city selector)
  dist/<code>/index.html    — per-city events page
  dist/<code>/data/seen_events.json — persisted from cities/<code>/data/
"""
from __future__ import annotations
import argparse, html as html_mod, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).parent.parent
CITIES_DIR = REPO_ROOT / "cities"
DIST = REPO_ROOT / "dist"


def discover_cities() -> list[dict]:
    sites = []
    for site_yaml in sorted(CITIES_DIR.glob("*/site.yaml")):
        site = yaml.safe_load(site_yaml.read_text(encoding="utf-8")) or {}
        site["_path"] = site_yaml
        sites.append(site)
    return sites


def build_city(site: dict, verbose: bool = False) -> int:
    out_dir = DIST / site["code"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_html = out_dir / "index.html"
    cmd = [sys.executable, str(REPO_ROOT / "tools/rebuild_calendar.py"),
           "--site-yaml", str(site["_path"]),
           "--out", str(out_html)]
    if verbose:
        cmd.append("--verbose")
    print(f"\n=== Building {site['code']} ({site['name']}) ===")
    rc = subprocess.call(cmd)
    if rc == 0 and out_html.exists():
        print(f"  -> {out_html}  ({out_html.stat().st_size:,} bytes)")
    else:
        print(f"  ! FAILED (rc={rc})", file=sys.stderr)
    return rc


def write_landing(sites: list[dict]) -> None:
    """Top-level dist/index.html — picks a city."""
    cards = []
    for s in sites:
        flag = s.get("flag", "")
        name = s.get("name", s["code"])
        eb = s.get("header_eyebrow", "")
        title = s.get("title", "")
        cards.append(f"""    <a class="city-card" href="{s['code']}/">
      <div class="city-flag">{flag}</div>
      <h2>{html_mod.escape(name)}</h2>
      <p class="city-eyebrow">{html_mod.escape(eb)}</p>
      <p class="city-title">{html_mod.escape(title)}</p>
    </a>""")
    cards_html = "\n".join(cards)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    landing = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What's on — pick a city</title>
<style>
  :root {{
    --bg:#fafafa; --fg:#181818; --muted:#666; --card:#fff; --line:#e5e5e5;
    --accent:#0a8a72;
  }}
  @media (prefers-color-scheme:dark){{
    :root {{--bg:#161616;--fg:#f5f5f5;--muted:#aaa;--card:#1f1f1f;--line:#333;}}
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;padding:48px 24px;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--fg)}}
  .wrap{{max-width:1100px;margin:0 auto}}
  h1{{font-size:34px;margin:0 0 8px;font-weight:700}}
  .sub{{color:var(--muted);margin:0 0 36px}}
  .city-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}}
  .city-card{{
    background:var(--card);border:1px solid var(--line);border-radius:16px;
    padding:24px 22px;text-decoration:none;color:inherit;display:block;
    transition:transform 0.15s, box-shadow 0.15s;
  }}
  .city-card:hover{{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,0.08);border-color:var(--accent)}}
  .city-flag{{font-size:48px;margin-bottom:8px;line-height:1}}
  .city-card h2{{font-size:22px;margin:0 0 4px;font-weight:600}}
  .city-eyebrow{{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:0.06em;margin:0 0 6px;font-weight:600}}
  .city-title{{color:var(--muted);font-size:13px;margin:0;line-height:1.4}}
  footer{{margin-top:48px;color:var(--muted);font-size:12px;text-align:center}}
  footer a{{color:var(--muted)}}
</style>
</head>
<body>
<div class="wrap">
  <h1>What's on</h1>
  <p class="sub">A weekly cultural-events calendar — pick a city.</p>
  <div class="city-grid">
{cards_html}
  </div>
  <footer>
    Rebuilt {now} ·
    <a href="https://fengelh2.github.io/events-stats/">stats</a> ·
    <a href="https://github.com/fengelh2/events">github</a>
  </footer>
</div>
</body>
</html>
"""
    (DIST / "index.html").write_text(landing, encoding="utf-8")
    print(f"\nLanding page -> {DIST / 'index.html'}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", help="Build only these city codes")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    sites = discover_cities()
    if args.only:
        sites = [s for s in sites if s["code"] in args.only]
        if not sites:
            print(f"No cities match {args.only}", file=sys.stderr)
            return 1

    DIST.mkdir(exist_ok=True)
    fails = 0
    for s in sites:
        if build_city(s, verbose=args.verbose) != 0:
            fails += 1

    write_landing(discover_cities())  # landing always lists all cities

    print(f"\n=== Done: {len(sites) - fails}/{len(sites)} cities built ===")
    # Partial failure → exit 0 (deploy good cities, gh-pages restore covers rest).
    # Total failure → exit 1 (mark CI red; don't silently deploy stale dist).
    return 1 if fails == len(sites) else 0


if __name__ == "__main__":
    sys.exit(main())
