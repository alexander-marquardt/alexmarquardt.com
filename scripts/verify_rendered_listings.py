#!/usr/bin/env python3
"""Check what the BUILT pages publish against the image files on disk.

    hugo --minify
    python3 scripts/verify_rendered_listings.py

**An exit code proves nothing here, which is why this exists.** The asset pages
are generated from the filesystem inside a template, and a template that walks
it wrongly returns an empty slice rather than an error: the page renders "No
images in this directory yet.", the build succeeds, and the deploy publishes
it. That has happened twice on this site.

* A listing built from Hugo's page tree came out EMPTY on the version CI pins,
  because the taxonomy configuration makes a top-level section a ``term`` there
  and a ``term`` has no ``.Pages``. It rendered fine on the newer Hugo the
  change was written against.
* A listing that read one directory level came out empty for a section whose
  images are in subdirectories -- which is every industrial drawing, one per
  product line under ``<product type>/<product id>/``.

Neither is visible in a build log. Four things are checked, all on the BUILT
output, so this measures the artefact that would be deployed rather than the
template that produced it:

1. **Every image directory has a page at the path that mirrors it.** Stripping
   the filename off an image URL must land on the page listing that directory,
   and stripping another segment must land on its parent.
2. **The path is matched CASE-SENSITIVELY**, by listing each parent directory
   and comparing names, never by ``Path.exists()``. Hugo lowercases a page's
   path when it derives a URL from it, so a page for ``OST-K663-0001/`` is
   published at ``ost-k663-0001/`` unless the adapter sets ``url`` explicitly.
   On Linux that is a second directory beside the images and the mirror is
   broken; on macOS the two collapse into one and the breakage is INVISIBLE
   locally while CI publishes it. ``Path.exists()`` returns True for both.
3. **Every page lists what its directory holds** -- the entry count in the
   rendered HTML against the files on disk, which is the empty-listing check.
   A page listing directories is counted against its children, and one showing
   a small set in full against the images below it; which of the two a page
   built is read off the page, not assumed from its depth.
4. **No image moved.** The set of image files published under ``images/`` must
   equal the set in the static tree, byte-identical paths. The page hierarchy
   was moved to mirror the files precisely so that no image URL would change,
   so that is asserted rather than intended.

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
#: The two-level caption `asset-grid.html` renders only when a cell carries a
#: `labelhref`. `list.html` passes one from exactly one branch -- the small-set
#: branch, which shows every image BELOW a directory of directories rather than
#: one cover per child -- so its presence identifies which listing was built.
#: Matched rather than assumed, because the threshold that selects the branch
#: lives in the layout and a copy of it here would be a second rule to keep in
#: step with the first.
CELL_LABEL = re.compile(r'class="?asset-label"?')
#: What Hugo writes for an alias: a meta-refresh stub, not a listing.
ALIAS = re.compile(r'http-equiv="?refresh"?', re.IGNORECASE)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

#: How deep the page tree went before it was moved under ``images/``. Those
#: URLs were published, so they must keep resolving -- as the page itself or
#: as a redirect to it.
LEGACY_DEPTH = 2


def images_under(directory: Path) -> set[Path]:
    return {
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }


def resolve_exactly(root: Path, parts: tuple[str, ...]) -> Path | None:
    """``root`` / ``parts``, matching each segment's case exactly.

    ``Path.exists()`` is case-INSENSITIVE on macOS and on Windows, so it
    answers True for a page Hugo published at a lowercased path while the
    images sit at the published one. That is the failure this function exists
    to see: it is the difference between a mirror that works on the deploy and
    one that only works on the machine it was checked on.
    """
    here = root
    for part in parts:
        if not here.is_dir():
            return None
        if part not in {entry.name for entry in here.iterdir()}:
            return None
        here = here / part
    return here


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, default=Path("public"))
    parser.add_argument(
        "--static", type=Path, default=Path("static/ecommerce-demo-assets/images")
    )
    parser.add_argument("--section", default="ecommerce-demo-assets")
    args = parser.parse_args(argv)

    section_root = args.public / args.section
    if not section_root.is_dir():
        print(f"{section_root} does not exist -- build the site first", file=sys.stderr)
        return 2
    if not args.static.is_dir():
        print(f"{args.static} does not exist", file=sys.stderr)
        return 2

    mirror_root = section_root / "images"
    problems = 0

    # --- 4: no image moved ------------------------------------------------
    static_images = {p.relative_to(args.static) for p in images_under(args.static)}
    published_images = (
        {p.relative_to(mirror_root) for p in images_under(mirror_root)}
        if mirror_root.is_dir()
        else set()
    )
    print(f"image files: {len(static_images)} on disk, {len(published_images)} published")
    if static_images != published_images:
        problems += 1
        gone = sorted(str(p) for p in static_images - published_images)
        extra = sorted(str(p) for p in published_images - static_images)
        print(f"  MISMATCH: {len(gone)} not published, {len(extra)} published from nowhere")
        for path in gone[:5]:
            print(f"    missing: {path}")
        for path in extra[:5]:
            print(f"    unexpected: {path}")
    else:
        print("  every image on disk is published at exactly its own path, and nothing else is")

    # --- 1-3: a page per image directory, mirrored, listing what it holds --
    directories = [args.static] + sorted(p for p in args.static.rglob("*") if p.is_dir())
    print(f"\n{'page':<64}{'listed':>8}{'expected':>10}")
    print("-" * 82)
    checked = 0
    leaf_cells = 0
    for directory in directories:
        relative = directory.relative_to(args.static)
        parts = relative.parts
        page_dir = resolve_exactly(mirror_root, parts)
        label = "images/" + ("/".join(parts) + "/" if parts else "")
        if page_dir is None or not (page_dir / "index.html").is_file():
            print(f"{label:<64}{'NO PAGE':>8}{len(images_under(directory)):>10}")
            print(
                f"  no page at the mirrored path. Walking up from an image URL in "
                f"this directory lands on a 404."
            )
            problems += 1
            continue

        html = (page_dir / "index.html").read_text(encoding="utf-8")
        on_disk = len(images_under(directory))
        subdirs = sorted(p for p in directory.iterdir() if p.is_dir())
        cells = len(CELL.findall(html))
        rows = len(INDEX_ROW.findall(html))
        # A directory of directories gets an index listing its children; a
        # directory of files gets a gallery listing every image at or below it.
        listed = cells if cells else rows
        # ...except that a directory of directories small enough to take in at
        # once is shown at once, as every image below it rather than one cover
        # per child. That is a third shape, and expecting one entry per child
        # for it fails a page that is listing MORE than it was asked to, not
        # less. The shape is read off the built HTML -- only that branch
        # captions a cell with the directory it came from -- so each shape is
        # still checked against one exact number rather than the gate being
        # relaxed to accept either.
        shows_every_image = bool(subdirs) and bool(CELL_LABEL.search(html))
        if shows_every_image:
            expected = on_disk
        else:
            expected = len(subdirs) if subdirs else on_disk
        if not subdirs:
            leaf_cells += cells
        checked += 1
        flag = "" if listed == expected else "  <-- MISMATCH"
        print(f"{label:<64}{listed:>8}{expected:>10}{flag}")
        if listed != expected:
            problems += 1
        if on_disk and not listed:
            print(
                f"  {label} holds {on_disk} image(s) and its page lists none. "
                "That is the empty-listing failure, and the build did not fail."
            )

    print(f"\nleaf pages list {leaf_cells} image(s); {len(static_images)} exist")
    if leaf_cells != len(static_images):
        problems += 1
        print("  MISMATCH: an image is in no gallery, so nothing on the site links to it")

    # --- 2 (the other half): the URLs that existed before the move --------
    print("\nlegacy page URLs:")
    legacy = [
        p.relative_to(args.static)
        for p in directories
        if p != args.static and len(p.relative_to(args.static).parts) <= LEGACY_DEPTH
    ]
    for relative in legacy:
        page = resolve_exactly(section_root, relative.parts)
        target = "/".join(("", args.section, "images", *relative.parts)) + "/"
        if page is None or not (page / "index.html").is_file():
            print(f"  GONE     /{args.section}/{relative}/ -- a published URL now 404s")
            problems += 1
            continue
        html = (page / "index.html").read_text(encoding="utf-8")
        if ALIAS.search(html):
            kind = "redirect" if target in html else "REDIRECTS ELSEWHERE"
            if kind != "redirect":
                problems += 1
        else:
            kind = "page"
        print(f"  {kind:<8} /{args.section}/{relative}/")

    print(f"\n{checked} page(s) checked, {problems} problem(s)")
    if problems:
        print(
            "\nA page listing fewer entries than its directory holds is published as a "
            "page that is simply missing them, and a mirrored path that does not exist "
            "is a 404 at the end of a URL somebody walked up. Nothing else in the build "
            "reports either."
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
