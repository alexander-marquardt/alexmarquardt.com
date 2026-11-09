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
# The industrial drawings are a FROZEN SAMPLE: 181 product lines (about 15
# per product type), from an earlier version of the generator that drew one PNG
# per product line. They are not republished. The current generator draws one
# SVG per SKU and ships them as a release bundle that a demo serves itself, so
# no demo should point at this site's drawings. The importer that copied them
# here, its URL check and its tests were removed with the trim (issues #14 and
# #15).
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
