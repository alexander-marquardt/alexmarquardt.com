#!/usr/bin/env python3
"""Check the catalog's image URLs against the files this site actually hosts.

    python3 scripts/verify_industrial_urls.py \
        --catalog ../synthetic-industrial-products/out/catalog/flat.jsonl

Two set comparisons, both directions, because each catches a different defect:

* **A URL with no file** is a broken image in every demo that renders the
  catalog. This is the one a spot check misses: the image reference is not the
  product's own SKU for about three records in four, so a URL built from the
  wrong field is dead at that rate while the handful of records anyone checks
  by hand may be exactly the ones where the two agree.
* **A file no record points at** is dead weight in a repository that is cloned
  in full on every build, and usually means a stale import.

Exit status is non-zero if either set is non-empty, so this can gate a commit.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

DEFAULT_PREFIX = "https://alexmarquardt.com/ecommerce-demo-assets/images/industrial/"
STATIC_ROOT = Path("static/ecommerce-demo-assets/images/industrial")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="flat.jsonl")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument(
        "--allow-undrawn",
        action="store_true",
        help="report URLs with no file but do not fail on them (renders still in flight)",
    )
    args = parser.parse_args(argv)

    prefix = args.prefix if args.prefix.endswith("/") else args.prefix + "/"
    static_root = args.root / STATIC_ROOT

    wanted: Counter[str] = Counter()
    records = records_with_image = 0
    foreign: set[str] = set()
    for line in args.catalog.open(encoding="utf-8"):
        if not line.strip():
            continue
        record = json.loads(line)
        records += 1
        urls = record.get("image_urls") or []
        if urls:
            records_with_image += 1
        for url in urls:
            if not url.startswith(prefix):
                foreign.add(url)
                continue
            wanted[urllib.parse.unquote(url[len(prefix) :])] += 1

    hosted = {
        str(path.relative_to(static_root)) for path in static_root.rglob("*.png")
    }

    missing = sorted(set(wanted) - hosted)
    unreferenced = sorted(hosted - set(wanted))

    print(f"catalog records          : {records}")
    print(f"  carrying an image URL  : {records_with_image}")
    print(f"  carrying none          : {records - records_with_image}")
    print(f"distinct URLs referenced : {len(wanted)}")
    print(f"files hosted             : {len(hosted)}")
    print(f"URLs with no file        : {len(missing)}")
    print(f"files no record points at: {len(unreferenced)}")

    if foreign:
        print(f"\nURLs outside {prefix} : {len(foreign)}")
        for url in sorted(foreign)[:5]:
            print(f"  {url}")

    if missing:
        affected = sum(wanted[path] for path in missing)
        print(f"\nDEAD LINKS: {len(missing)} URL(s), referenced {affected} time(s)")
        for path in missing[:10]:
            print(f"  {path}  ({wanted[path]} record(s))")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

    if unreferenced:
        print(f"\nUNREFERENCED: {len(unreferenced)} hosted file(s)")
        for path in unreferenced[:10]:
            print(f"  {path}")
        if len(unreferenced) > 10:
            print(f"  ... and {len(unreferenced) - 10} more")

    failed = bool(unreferenced) or bool(foreign) or (bool(missing) and not args.allow_undrawn)
    print("\n" + ("FAIL" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
