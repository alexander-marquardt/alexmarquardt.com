#!/usr/bin/env python3
"""Publish the synthetic industrial catalog's drawings into this site.

    python3 scripts/import_industrial_images.py \
        --manifest ../synthetic-industrial-products/out/images.jsonl \
        --images   ../synthetic-industrial-products/out/images

Re-runnable. A second run with more drawings available adds them and leaves
everything else alone; no page needs editing, because every listing on the
site is read off this directory at build time.

**Where each file goes is read from the generator's manifest, not worked out
here.** An image reference is not the referring product's SKU, and the product
type in its URL is the type of the product DRAWN, which reuse lets differ from
the type of the product referencing it. That rule lives in the generator; a
second copy here is how the two would come to disagree. This script therefore
reads the manifest's own ``path`` and ``detail_path`` and writes exactly there,
whatever shape they take.

Both profiles are published. The card is what a catalog listing shows and the
detail is what a product page shows, and the catalog's records carry a URL for
each -- so hosting only one leaves every ``image_detail_url`` in the catalog a
dead link. Ten drawings at both profiles measure 964 KiB before compression;
the "hundreds of megabytes" this script once cited as the reason to skip the
detail set was the cost of a drawing PER SKU, which the ten generics replaced.

Compression is lossy palette quantisation followed by a lossless pass. On these
drawings -- flat white with thin strokes and a few flat fills -- it holds around
a 76% saving with no visible difference at either size the images are displayed
at. The quantiser is run without dithering, which both looks better on flat art
and compresses harder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

#: Quality floor/ceiling for the quantiser. Below about 65 the antialiasing on
#: the thin strokes starts to posterise at 150px.
QUALITY = "65-90"

DEST_ROOT = Path("static/ecommerce-demo-assets/images/industrial")

#: The manifest keys naming a file to publish, in the order they are published.
#: Each is a path relative to :data:`DEST_ROOT`; the profile is read back off
#: the path rather than assumed, so the generator stays the only place that
#: decides what the published tree looks like.
PATH_KEYS = ("path", "detail_path")

#: What the generator has called an image's reference, newest spelling first.
#: The manifest emits ``image_id``; ``image_ref`` is an older spelling, and
#: reading only one of them is what made this script fail on row one against a
#: manifest it was supposedly written for.
REF_KEYS = ("image_id", "image_ref")


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        sys.exit(
            f"{tool} is not installed. brew install oxipng pngquant "
            "(or apt-get install oxipng pngquant)"
        )


def image_ref(row: dict) -> str:
    """The manifest row's reference to its drawing, under whichever key it uses.

    Tried in order rather than hardcoded, for the same reason the filename
    spellings below are: the generator and this script are separate
    repositories, each with its own tests, and a key renamed on one side is
    otherwise found only by running the publish end to end.
    """
    for key in REF_KEYS:
        if key in row:
            return str(row[key])
    raise KeyError(
        f"manifest row names its drawing under none of {REF_KEYS}; it carries "
        f"{sorted(row)}. If the generator renamed the key, add the new spelling "
        "to REF_KEYS."
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


def _source_for(images: Path, row: dict, published: str, suffix: str | None = None) -> Path | None:
    """The rendered file for one published path, whatever the renderer named it.

    The renderer has named its output differently at different times -- per-SKU
    ``<sku>_card.png``, and a generic named for what it draws rather than for
    any one SKU. The manifest is the authority on where a file GOES; this only
    has to find it, so it tries the spellings rather than assuming one.

    The profile is read off the published path rather than passed in, so the
    generator's naming decision reaches this script through the manifest
    instead of through a constant kept in step by hand.
    """
    ref = image_ref(row)
    profile = Path(published).stem
    candidates = [
        f"{ref}_{profile}.png",  # sip-render generics --profile both
        f"{ref}.png",  # a renderer that wrote one profile only
        published,  # a source tree already in the published layout
        Path(published).name,
    ]
    if suffix:
        candidates.insert(0, f"{ref}{suffix}")
    for name in candidates:
        candidate = images / name
        if candidate.exists():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="images.jsonl")
    parser.add_argument(
        "--images",
        "--cards",
        dest="images",
        type=Path,
        required=True,
        help="directory the renderer wrote its PNGs to",
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument(
        "--force", action="store_true", help="re-compress images already published"
    )
    parser.add_argument(
        "--suffix",
        default=None,
        help="try this suffix on the image reference first, for a renderer "
        "whose output this script does not otherwise recognise",
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
        for key in PATH_KEYS:
            if key not in row:
                continue
            dest = dest_root / row[key]
            published.add(dest)
            source = _source_for(args.images, row, row[key], args.suffix)
            if source is None:
                missing.append(f"{image_ref(row)} ({row[key]})")
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
        for path in sorted(dest_root.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    on_disk = sorted(dest_root.rglob("*.png")) if dest_root.exists() else []
    orphans = [p for p in on_disk if p not in published]

    print(f"manifest rows      : {len(rows)}")
    print(f"files the manifest publishes: {len(published)}")
    print(f"written            : {written}")
    print(f"already published  : {skipped}")
    print(f"pruned             : {pruned}")
    print(f"files on disk      : {len(on_disk)}")
    print(f"published under    : {dest_root}")
    if missing:
        print(
            f"\nNOT YET DRAWN      : {len(missing)} of {len(published)} published paths have "
            f"no render in {args.images}"
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
