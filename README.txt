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
# So adding images, a category, or a whole section needs no edit to any
# content file. data/asset_sections.yaml optionally adds a sentence of
# provenance to a section; it never lists a file.
#
# To publish more drawings from the synthetic industrial catalog:
#
#   python3 scripts/import_industrial_images.py \
#       --manifest ../synthetic-industrial-products/out/catalog/images.jsonl \
#       --cards    ../synthetic-industrial-products/out/images/card
#   python3 scripts/verify_industrial_urls.py \
#       --catalog  ../synthetic-industrial-products/out/catalog/flat.jsonl
#
# The first compresses and files each drawing under its product type; the
# second checks, both directions, that every URL the catalog emits has a file
# here and that every file here is pointed at. Both are re-runnable.
# They need pngquant and oxipng: brew install pngquant oxipng
