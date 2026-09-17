"""The seam between the catalog generator and this site's importer.

    python3 -m pytest tests/

These two repositories were built against each other's *expected* shapes and
did not mesh: the importer read ``row['image_ref']`` from a manifest that emits
``image_id``, so the publish died with ``KeyError`` on the first row. Neither
side's tests caught it, because each tested its own assumption -- the generator
proved it emits what it emits, and the importer was exercised against rows
written by hand here to match what this file believed the generator emitted.

So the fixture these tests read is **not written here**. ``fixtures/images.jsonl``
is a byte-for-byte copy of ``out/images.jsonl`` from a
``sip-generate build`` run of the generator, and
:func:`test_the_fixture_is_what_the_generator_currently_emits` re-runs the
generator and compares, whenever a checkout of it is next door. A hand-written
fixture would restore the exact defect these tests exist to close: it would
agree with whatever this file assumes, which is the thing that was wrong.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "images.jsonl"


def _load_importer():
    spec = importlib.util.spec_from_file_location(
        "import_industrial_images", REPO / "scripts" / "import_industrial_images.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


importer = _load_importer()


@pytest.fixture(scope="module")
def manifest_rows() -> list[dict]:
    rows = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    assert rows, "the fixture is the generator's real output and is not empty"
    return rows


# --- the key the manifest actually emits -----------------------------------


def test_every_row_of_the_real_manifest_yields_an_image_reference(manifest_rows):
    """The defect, directly: this raised ``KeyError: 'image_ref'`` on row one.

    Asserted over every row rather than the first, because a manifest whose
    rows disagreed about their keys would otherwise pass here and fail part way
    through a publish, having already written some of the files.
    """
    for row in manifest_rows:
        assert importer.image_ref(row)


def test_the_manifest_emits_image_id_and_the_importer_reads_that_key(manifest_rows):
    """Names the key that broke, so a rename on either side reds HERE.

    The test above would keep passing if the generator went back to
    ``image_ref``; this one records which spelling is live, so the pair fails
    loudly instead of the site quietly importing from an older shape.
    """
    for row in manifest_rows:
        assert "image_id" in row, "the live spelling"
        assert importer.image_ref(row) == row["image_id"]


def test_the_older_spelling_is_still_accepted():
    """Tolerance goes both ways: an older manifest still publishes."""
    assert importer.image_ref({"image_ref": "washer_flat"}) == "washer_flat"


def test_a_row_naming_its_drawing_under_no_known_key_says_so(manifest_rows):
    """And says which keys it does carry, rather than raising a bare KeyError."""
    stripped = {k: v for k, v in manifest_rows[0].items() if k not in importer.REF_KEYS}
    with pytest.raises(KeyError) as caught:
        importer.image_ref(stripped)
    assert "image_id" in str(caught.value), "the message names the keys it looked for"


# --- the published layout ---------------------------------------------------


def test_the_manifest_files_each_drawing_under_its_product_type(manifest_rows):
    """One directory per product type, one file per profile inside it.

    This is the structure the site's own pages are built from: the industrial
    index lists the directories as categories and each category page lists the
    files in it. Filed the other way -- ``card/`` and ``detail/`` holding every
    product type -- the index would offer two categories named after image
    sizes, which is what it did before.
    """
    for row in manifest_rows:
        product_type = row["product_type"]
        assert row["path"] == f"{product_type}/card.png"
        assert row["detail_path"] == f"{product_type}/detail.png"


def test_the_manifest_publishes_both_profiles_and_the_importer_writes_both(manifest_rows):
    """A record carries a card URL and a detail URL; hosting one kills the other."""
    assert set(importer.PATH_KEYS) == {"path", "detail_path"}
    for row in manifest_rows:
        for key in importer.PATH_KEYS:
            assert key in row


def test_every_published_path_is_relative_and_stays_under_the_destination(manifest_rows):
    """A manifest is read from another repository; it does not get to escape this one."""
    for row in manifest_rows:
        for key in importer.PATH_KEYS:
            path = Path(row[key])
            assert not path.is_absolute()
            assert ".." not in path.parts


# --- the importer against the real manifest, end to end ---------------------


def _renderer_output(tmp_path: Path, rows: list[dict]) -> Path:
    """A directory named the way ``sip-render generics --profile both`` names it.

    The filenames come from the manifest's own paths -- ``<ref>_<profile>.png``
    where the profile is the published file's stem -- so this does not hardcode
    a second copy of the renderer's convention either.
    """
    images = tmp_path / "rendered"
    images.mkdir()
    for row in rows:
        ref = importer.image_ref(row)
        for key in importer.PATH_KEYS:
            profile = Path(row[key]).stem
            (images / f"{ref}_{profile}.png").write_bytes(_PNG)
    return images


#: The smallest valid PNG: 1x1, fully transparent. The importer shells out to
#: pngquant and oxipng, which have to be given something they can parse.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000b49444154789c6360000200000500017a5eab3f0000"
    "000049454e44ae426082"
)


@pytest.mark.skipif(
    shutil.which("pngquant") is None or shutil.which("oxipng") is None,
    reason="pngquant and oxipng are what the importer compresses with",
)
def test_the_importer_publishes_the_real_manifest_to_the_paths_it_declares(
    tmp_path, manifest_rows, capsys
):
    """End to end on the generator's real output -- the run that found the defect.

    Asserts the set of files written is EXACTLY the set the manifest declares,
    both directions. A subset check would pass a publish that wrote the card
    and silently skipped every detail.
    """
    images = _renderer_output(tmp_path, manifest_rows)
    root = tmp_path / "site"
    (root / importer.DEST_ROOT).mkdir(parents=True)

    assert (
        importer.main(
            ["--manifest", str(FIXTURE), "--images", str(images), "--root", str(root)]
        )
        == 0
    )

    dest_root = root / importer.DEST_ROOT
    written = {str(p.relative_to(dest_root)) for p in dest_root.rglob("*.png")}
    declared = {row[key] for row in manifest_rows for key in importer.PATH_KEYS}
    assert written == declared, "every declared path written, and nothing else"
    assert len(declared) == 2 * len(manifest_rows), "both profiles, every drawing"

    out = capsys.readouterr().out
    assert "NOT YET DRAWN" not in out
    assert "HOSTED BUT UNREFERENCED" not in out


@pytest.mark.skipif(
    shutil.which("pngquant") is None or shutil.which("oxipng") is None,
    reason="pngquant and oxipng are what the importer compresses with",
)
def test_a_second_run_republishes_nothing(tmp_path, manifest_rows, capsys):
    """Re-runnable is a documented property of this script, so it is checked."""
    images = _renderer_output(tmp_path, manifest_rows)
    root = tmp_path / "site"
    (root / importer.DEST_ROOT).mkdir(parents=True)
    argv = ["--manifest", str(FIXTURE), "--images", str(images), "--root", str(root)]

    importer.main(argv)
    capsys.readouterr()
    importer.main(argv)
    second = capsys.readouterr().out

    assert "written            : 0" in second
    assert f"already published  : {2 * len(manifest_rows)}" in second


@pytest.mark.skipif(
    shutil.which("pngquant") is None or shutil.which("oxipng") is None,
    reason="pngquant and oxipng are what the importer compresses with",
)
def test_a_drawing_the_renderer_has_not_written_is_reported_not_guessed(
    tmp_path, manifest_rows, capsys
):
    """The publish continues and names what is missing, rather than dying or faking it."""
    images = _renderer_output(tmp_path, manifest_rows)
    absent = importer.image_ref(manifest_rows[0])
    for stale in images.glob(f"{absent}_*.png"):
        stale.unlink()

    root = tmp_path / "site"
    (root / importer.DEST_ROOT).mkdir(parents=True)
    assert (
        importer.main(
            ["--manifest", str(FIXTURE), "--images", str(images), "--root", str(root)]
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "NOT YET DRAWN" in out
    assert absent in out
    dest_root = root / importer.DEST_ROOT
    written = {str(p.relative_to(dest_root)) for p in dest_root.rglob("*.png")}
    assert not any(path.startswith(f"{absent}/") for path in written)


# --- the fixture is the generator's, not ours -------------------------------


def _generator_checkout() -> Path | None:
    override = os.environ.get("SIP_GENERATOR")
    candidates = [Path(override)] if override else []
    candidates.append(REPO.parent / "synthetic-industrial-products")
    for path in candidates:
        if (path / "src" / "synthetic_industrial_products").is_dir():
            return path
    return None


def test_the_fixture_is_what_the_generator_currently_emits(tmp_path):
    """Re-run the generator and compare, so the fixture cannot quietly go stale.

    Skipped when no checkout of the generator is next door, which is the normal
    case in this site's CI -- a site build does not depend on the generator. It
    is not skipped where it matters: on the machine of whoever is publishing a
    fresh catalog, which is the moment the two shapes can diverge.

    Set ``SIP_GENERATOR`` to point at a checkout elsewhere.
    """
    generator = _generator_checkout()
    if generator is None:
        pytest.skip("no checkout of synthetic-industrial-products alongside this repo")

    build = subprocess.run(
        ["uv", "run", "sip-generate", "build", "--out", str(tmp_path)],
        cwd=generator,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        pytest.skip(f"could not run the generator: {build.stderr[-400:]}")

    emitted = (tmp_path / "images.jsonl").read_text()
    assert emitted == FIXTURE.read_text(), (
        "tests/fixtures/images.jsonl is stale. It is a verbatim copy of the "
        "generator's out/images.jsonl -- re-copy it rather than editing it, and "
        "check what changed about the manifest's shape before you do."
    )


def test_the_fixture_is_not_hand_written(manifest_rows):
    """A guard on the guard: the fixture must carry the generator's whole shape.

    If it were trimmed to the fields these tests read, it would stop being
    evidence about the generator and go back to being this file's assumption
    about it, which is the defect.
    """
    expected = {"image_id", "product_type", "path", "url", "detail_path", "detail_url",
                "referenced_by"}
    for row in manifest_rows:
        assert set(row) == expected
        assert row["referenced_by"] > 1, "a drawing is shared by a family"
        assert row["url"].endswith(row["path"])
        assert row["detail_url"].endswith(row["detail_path"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
