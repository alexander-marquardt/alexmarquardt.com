#!/usr/bin/env python3
"""Count what the built pages actually list, and compare it to the files on disk.

    hugo --minify
    python3 scripts/verify_rendered_listings.py

**An exit code proves nothing here, which is why this exists.** The asset
listings are built by walking the filesystem inside a template, and a template
that walks it wrongly returns an empty slice rather than an error: the page
renders "No images in this directory yet.", the build succeeds, and the deploy
publishes it. That has happened twice on this site.

* A listing built from Hugo's page tree came out EMPTY on the version CI pins,
  because the taxonomy configuration makes a top-level section a ``term`` there
  and a ``term`` has no ``.Pages``. It rendered fine on the newer Hugo the
  change was written against.
* A listing that read one directory level came out empty for a section whose
  images are in subdirectories -- which is every industrial drawing, one per
  product line under ``<product type>/<product id>/``.

Neither is visible in a build log. Both are visible in one number: how many
entries the rendered HTML carries against how many image files are on disk
under the directory that page describes. That is what this counts, on the
BUILT output, so it is measuring the artefact that would be deployed rather
than the template that produced it.

Run it against the pinned Hugo. A pass on a newer one says nothing about what
CI will publish.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: One rendered thumbnail in `asset-grid.html`.
CELL = re.compile(r'class="?asset-cell"?')
#: One rendered row in a category index in `list.html`.
INDEX_ROW = re.compile(r'class="?asset-count"?')

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def images_under(directory: Path) -> int:
    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, default=Path("public"))
    parser.add_argument(
        "--static",
        type=Path,
        default=Path("static/ecommerce-demo-assets/images"),
    )
    parser.add_argument("--section", default="ecommerce-demo-assets")
    args = parser.parse_args(argv)

    pages = args.public / args.section
    if not pages.is_dir():
        print(f"{pages} does not exist -- build the site first", file=sys.stderr)
        return 2
    if not args.static.is_dir():
        print(f"{args.static} does not exist", file=sys.stderr)
        return 2

    sections = sorted(p for p in args.static.iterdir() if p.is_dir())
    if not sections:
        print(f"no image directories under {args.static}", file=sys.stderr)
        return 2

    problems = 0
    checked = 0
    print(f"{'page':<52}{'listed':>8}{'on disk':>9}")
    print("-" * 69)
    for section in sections:
        children = sorted(p for p in section.iterdir() if p.is_dir())
        # A section holding directories gets an index page plus one page per
        # directory; a section holding files gets one page. Both shapes are
        # checked, because a section that changes shape is exactly when a
        # listing goes quietly empty.
        targets = [(section, children)] + [(child, []) for child in children]
        for directory, subdirs in targets:
            relative = directory.relative_to(args.static)
            page = pages / relative / "index.html"
            if not page.is_file():
                print(f"{str(relative):<52}{'NO PAGE':>8}{images_under(directory):>9}")
                problems += 1
                continue
            html = page.read_text(encoding="utf-8")
            on_disk = images_under(directory)
            cells = len(CELL.findall(html))
            rows = len(INDEX_ROW.findall(html))
            # An index page lists its child directories rather than the files;
            # a gallery page lists every file at or below it. Whichever shape
            # the page took, the number it shows has to be the number there is.
            listed = cells if cells else rows
            expected = on_disk if cells or not subdirs else len(subdirs)
            checked += 1
            flag = "" if listed == expected else "  <-- MISMATCH"
            print(f"{str(relative):<52}{listed:>8}{expected:>9}{flag}")
            if listed != expected:
                problems += 1
            if on_disk and not listed:
                print(
                    f"  {relative} holds {on_disk} image(s) and its page lists none. "
                    "That is the empty-listing failure, and the build did not fail."
                )

    print(f"\n{checked} page(s) checked, {problems} mismatch(es)")
    if problems:
        print(
            "\nA page listing fewer entries than the directory holds is published as "
            "a page that is simply missing them. Nothing else in the build reports it."
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
