#!/usr/bin/env python3
"""Publish the synthetic industrial catalog's card drawings into this site.

    python3 scripts/import_industrial_images.py \
        --manifest ../synthetic-industrial-products/out/catalog/images.jsonl \
        --cards    ../synthetic-industrial-products/out/images/card

Re-runnable. A second run with more drawings available adds them and leaves
everything else alone; no page needs editing, because every listing on the
site is read off this directory at build time.

**Where each file goes is read from the generator's manifest, not worked out
here.** An image reference is not the referring product's SKU, and the product
type in its URL is the type of the product DRAWN, which reuse lets differ from
the type of the product referencing it. That rule lives in the generator; a
second copy here is how the two would come to disagree.

Compression is lossy palette quantisation followed by a lossless pass. On the
card drawings -- flat white with thin strokes and a few flat fills -- it holds
around a 76% saving with no visible difference at either size the images are
displayed at. The dimension callouts are the legibility test, and they survive:
the quantiser is run without dithering, which both looks better on flat art and
compresses harder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

#: Card drawings only. The detail profile is 1400x1400; hosting that set would
#: add hundreds of megabytes to a repository that exists to serve 150px
#: thumbnails.
SOURCE_SUFFIX = "_card.png"

#: Quality floor/ceiling for the quantiser. Below about 65 the antialiasing on
#: the callout digits starts to posterise at 150px.
QUALITY = "65-90"

DEST_ROOT = Path("static/ecommerce-demo-assets/images/industrial")


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        sys.exit(
            f"{tool} is not installed. brew install oxipng pngquant "
            "(or apt-get install oxipng pngquant)"
        )


def compress(source: Path, dest: Path) -> None:
    """Quantise then losslessly re-pack, writing ``dest``.

    ``pngquant`` exits non-zero when it cannot reach the quality floor. That is
    a reason to ship the original, not a reason to ship nothing.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    quantised = subprocess.run(
        [
            "pngquant", "--nofs", f"--quality={QUALITY}", "--skip-if-larger",
            "--force", "--output", str(dest), "--", str(source),
        ],
        capture_output=True,
    )
    if quantised.returncode != 0:
        shutil.copyfile(source, dest)
    subprocess.run(["oxipng", "-o", "max", "--strip", "safe", "-q", str(dest)], check=True)


def _source_for(cards: Path, row: dict, suffix: str) -> Path | None:
    """The rendered file for one manifest row, whatever the renderer named it.

    The renderer has named its output differently at different times -- per-SKU
    ``<sku>_card.png``, and a generic named for what it draws rather than for
    any one SKU. The manifest is the authority on where a file GOES; this only
    has to find it, so it tries the spellings rather than assuming one.
    """
    candidates = (
        f"{row['image_ref']}{suffix}",
        f"{row['image_ref']}.png",
        Path(row["path"]).name,
        Path(row["path"]).stem + suffix,
    )
    for name in candidates:
        candidate = cards / name
        if candidate.exists():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="images.jsonl")
    parser.add_argument("--cards", type=Path, required=True, help="directory of *_card.png")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument(
        "--force", action="store_true", help="re-compress images already published"
    )
    parser.add_argument(
        "--suffix", default=SOURCE_SUFFIX, help="suffix the renderer puts on a card file"
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="delete published files the manifest no longer lists",
    )
    args = parser.parse_args(argv)

    _require("pngquant")
    _require("oxipng")

    dest_root = args.root / DEST_ROOT
    rows = [json.loads(line) for line in args.manifest.read_text().splitlines() if line.strip()]

    written = skipped = 0
    missing: list[str] = []
    published: set[Path] = set()
    for row in rows:
        dest = dest_root / row["path"]
        published.add(dest)
        source = _source_for(args.cards, row, args.suffix)
        if source is None:
            missing.append(row["image_ref"])
            continue
        if dest.exists() and not args.force:
            skipped += 1
            continue
        compress(source, dest)
        written += 1

    pruned = 0
    if args.prune:
        for path in sorted(dest_root.rglob("*.png")):
            if path not in published:
                path.unlink()
                pruned += 1

    on_disk = sorted(dest_root.rglob("*.png"))
    orphans = [p for p in on_disk if p not in published]

    print(f"manifest rows      : {len(rows)}")
    print(f"written            : {written}")
    print(f"already published  : {skipped}")
    print(f"pruned             : {pruned}")
    print(f"files on disk      : {len(on_disk)}")
    print(f"published under    : {dest_root}")
    if missing:
        print(
            f"\nNOT YET DRAWN      : {len(missing)} of {len(rows)} manifest rows have no "
            f"card render in {args.cards}"
        )
        print(f"  first few        : {', '.join(sorted(missing)[:8])}")
        print("  Re-run this script once those renders exist; nothing else needs changing.")
    if orphans:
        print(f"\nHOSTED BUT UNREFERENCED: {len(orphans)} file(s) the manifest does not list")
        for path in orphans[:8]:
            print(f"  {path.relative_to(dest_root)}")
        print("  Re-run with --prune to remove them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
