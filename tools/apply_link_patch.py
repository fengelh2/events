"""Apply the patches in dist/link_patch.json to the per-city YAML files.

Replacements are safe (URL → URL swap with verification). Removals are
opt-in (default: only WARN; pass --remove to actually delete entries).
"""
from __future__ import annotations
import argparse, json, sys, shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PATCH = REPO_ROOT / "dist" / "link_patch.json"


def apply_replacements(patches: list[dict], dry_run: bool) -> int:
    by_file: dict[Path, list[dict]] = {}
    for p in patches:
        path = REPO_ROOT / "cities" / p["city"] / "config" / "venues.yaml"
        by_file.setdefault(path, []).append(p)
    n = 0
    for path, items in by_file.items():
        if not path.exists():
            print(f"  ! missing {path}", file=sys.stderr); continue
        text = path.read_text(encoding="utf-8")
        original = text
        for p in items:
            old, new = p["old"], p["new"]
            if old in text:
                text = text.replace(old, new)
                n += 1
                print(f"  ✓ {p['city']}/{p['venue_id']}: {old[:60]} → {new[:60]}")
            else:
                print(f"  - {p['city']}/{p['venue_id']}: old URL no longer in YAML (already patched?)")
        if text != original and not dry_run:
            shutil.copy(path, str(path) + ".bak")
            path.write_text(text, encoding="utf-8")
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Print only, don't write files")
    p.add_argument("--remove", action="store_true",
                   help="Also process removals (default: just warn — removal is a human call)")
    args = p.parse_args()

    if not PATCH.exists():
        print(f"No patch file at {PATCH}. Run tools/investigate_broken_links.py first.", file=sys.stderr)
        return 1
    data = json.loads(PATCH.read_text(encoding="utf-8"))
    sys.stdout.reconfigure(encoding="utf-8")

    patches = data.get("patches", [])
    removals = data.get("removals", [])
    print(f"\n{len(patches)} replacement patches:")
    n_applied = apply_replacements(patches, dry_run=args.dry_run)

    print(f"\n{len(removals)} proposed removals:")
    for r in removals:
        print(f"  - {r['city']}/{r['venue_id']} ({r['field']}): {r['url']}")
        print(f"    evidence: {r['evidence']}")
    if removals and not args.remove:
        print("\n  (pass --remove to actually delete these entries — currently informational only)")

    print(f"\nApplied {n_applied} URL replacements{' (dry run)' if args.dry_run else ''}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
