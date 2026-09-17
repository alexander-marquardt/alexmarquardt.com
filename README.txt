# For local testing the following commands are useful
  rm -rf public/
  hugo server -D --baseURL http://localhost:1313/ --appendPort=false

# E-commerce demo assets
#
# The pages under /ecommerce-demo-assets/ are DERIVED, not written. The
# listings are read out of static/ecommerce-demo-assets/images/ at build time
# by content/ecommerce-demo-assets/_content.gotmpl and
# layouts/partials/asset-gallery.html:
#
#   a directory of images        -> one listing page
#   a directory of directories   -> an index, plus one listing page each
#
# ...except that when every child of a directory is itself a directory of
# PICTURES, the page shows one thumbnail per child -- the image named by
# demoAssets.cover -- linking to that child's page, rather than a list of
# links. These images exist to be looked at, and an index of a hundred product
# lines makes browsing five hundred drawings five hundred clicks. The index
# stays the answer where a child is a directory of DIRECTORIES, which has no
# single picture that stands for it.
#
# The tree is read to the BOTTOM, not to a fixed depth, so a section filed
# several levels deep -- the industrial drawings are one per product LINE,
# under <product type>/<product id>/ -- gets a page at every level.
#
# THE PAGE PATH MIRRORS THE FILE PATH. A directory's page is published at the
# URL its own images are served from:
#
#   /ecommerce-demo-assets/images/industrial/end_mill_square/OST-K663-0001/card.png
#   /ecommerce-demo-assets/images/industrial/end_mill_square/OST-K663-0001/   <- its page
#   /ecommerce-demo-assets/images/industrial/end_mill_square/                 <- its category
#   /ecommerce-demo-assets/images/industrial/                                 <- its section
#   /ecommerce-demo-assets/images/                                            <- the index
#
# so stripping segments off an image URL always lands on a page. Before this
# the two hierarchies merely shared names -- the files were under images/ and
# the pages were not -- and /ecommerce-demo-assets/images/industrial/ was a
# 404 while /ecommerce-demo-assets/industrial/ was a 200. The PAGES moved; no
# image URL changed, which is why it was done this way round. The old page
# URLs are kept alive as Hugo aliases (a redirect to the new one).
#
# The content adapter passes an explicit `url` for each page. Hugo lowercases
# a path it derives itself, and a product id is uppercase, so without it the
# page for OST-K663-0001/ is published at ost-k663-0001/ -- a second directory
# beside the images on Linux, and INVISIBLE on macOS, where the two collapse
# into one. scripts/verify_rendered_listings.py compares the paths
# case-sensitively for exactly that reason.
#
# So adding images, a category, or a whole section needs no edit to any
# content file. data/asset_sections.yaml optionally adds a sentence of
# provenance to a section; it never lists a file.
#
# To publish more drawings from the synthetic industrial catalog:
#
#   python3 scripts/import_industrial_images.py \
#       --manifest ../synthetic-industrial-products/out/catalog/images.jsonl \
#       --images   ../synthetic-industrial-products/out/images --prune
#   python3 scripts/verify_industrial_urls.py \
#       --catalog  ../synthetic-industrial-products/out/catalog/flat.jsonl
#
# The first compresses and files each drawing at the path the manifest
# declares; the second checks, both directions, that every URL the catalog
# emits has a file here and that every file here is pointed at. --prune
# removes files the manifest no longer lists, which is what a re-import after
# a change to the naming scheme needs. Both are re-runnable.
# They need pngquant and oxipng: brew install pngquant oxipng
#
# WHEN YOU REPUBLISH, THE URLS THAT DID NOT CHANGE ARE THE CONTROL -- AND ON
# THIS TREE THAT CONTROL IS ONE PRODUCT TYPE. The generator draws every builder
# from one RNG and one global index, so adding a product type re-cuts the
# shares and shifts every record after the point it was inserted. At the
# 2026-09-17 republish that moved 405 of 500 product lines; the 95 that held
# still were end_mill_square, and ALL 190 of its published paths were among
# them, while the other eleven types were 100% new files.
#
# So "the unchanged URLs still resolve" was, that time, a statement about
# end_mill_square and nothing else. Two things follow for the next republish:
#
#   * Check the unchanged set IN FULL rather than sampling it. It is small --
#     190 URLs -- and it is the half where a republish that quietly drops a
#     file does its damage, since a dropped file that nothing re-rendered
#     leaves no other trace.
#   * Work out which type the unchanged set belongs to BEFORE concluding
#     anything from it. A republish that shifts end_mill_square would leave no
#     unchanged control at all, and a run reporting "all unchanged URLs
#     resolve" over an EMPTY unchanged set is a vacuous pass that reads
#     exactly like a real one.
#
# Compare the old and new published sets straight from git rather than
# trusting the counts, which is what produced the figures above:
#
#   git ls-tree -r --name-only <old> -- static/ecommerce-demo-assets/images/industrial
#   git ls-tree -r --name-only <new> -- static/ecommerce-demo-assets/images/industrial
#
# and take comm -12 for the unchanged set and comm -13 for the new one. A file
# being present is not the check: fetch it and compare the response body's
# sha256 against the file in this repository. A 200 with the wrong bytes is
# exactly what a republish against a moved generator produces, and a
# status-code check cannot see it.
#
# A BUILD THAT SUCCEEDS IS NOT EVIDENCE THE PAGES LIST ANYTHING. Build on the
# version .hugo-version pins -- not on whatever brew installed; both workflows
# read that file -- and count what came out:
#
#   hugo --minify
#   python3 scripts/verify_rendered_listings.py
#
# It checks four things on the BUILT output: every image directory has a page
# at the path that mirrors it, matched case-sensitively; every page lists what
# its directory holds; every page URL that existed before the mirror still
# resolves; and the published image files are exactly the ones on disk, so a
# page change cannot move an image. Both workflows run it -- the tests one on
# every pull request, the deploy one before the artifact is uploaded.
