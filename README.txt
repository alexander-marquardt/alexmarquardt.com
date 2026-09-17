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
# A listing page lists every image AT OR BELOW its directory, so a section
# filed several levels deep -- the industrial drawings are one per product
# LINE, under <product type>/<product id>/ -- still lists all of them.
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
# A BUILD THAT SUCCEEDS IS NOT EVIDENCE THE PAGES LIST ANYTHING. Build on the
# version .github/workflows/hugo.yaml pins -- not on whatever brew installed --
# and count what came out:
#
#   hugo --minify
#   python3 scripts/verify_rendered_listings.py
#
# It compares the entries in each rendered page against the image files on
# disk under the directory that page describes. The deploy workflow runs it
# after the build, so an empty listing fails there instead of shipping.
