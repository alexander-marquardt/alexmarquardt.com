---
title: "E-commerce Demo Assets"
description: "Public image assets for e-commerce search demos and testing."
---

Publicly accessible images used for e-commerce search demos. They are served as
static files, so anything that can fetch a URL can use them — a demo catalog, a
test fixture, a notebook.

**Everything here is either a product photograph collected for demo use or a
drawing generated from synthetic data.** The industrial drawings are the second
kind: no photograph, no third-party artwork, and no model-generated imagery is
involved. Each one is drawn from the attribute values of a generated product
record by the [synthetic-industrial-products](https://github.com/alexander-marquardt/synthetic-industrial-products)
generator, which means the drawing cannot contradict the data it came from —
the products it depicts do not exist.

## Direct URL pattern

```
/ecommerce-demo-assets/images/<section>/<filename>
/ecommerce-demo-assets/images/industrial/<product-type>/<product-id>/<profile>.png
```

For example:

```
/ecommerce-demo-assets/images/electronics/apple-iphone-001.png
```

Every listing below is read from the directory it describes when the site is
built, so what you see there is what is actually hosted.

**The browse pages sit at the same paths as the files.** Strip the filename off
any image URL and you get the page listing that directory; strip another
segment and you get its parent, up to
[/ecommerce-demo-assets/images/](/ecommerce-demo-assets/images/). The older
page URLs, without `images/`, redirect to their new ones.

The industrial drawings hosted here are a browsable sample from an earlier
version of the generator, which drew **one drawing per product line**. That is
why the path carries a product type and then a product line, and why each
drawing has the line's published attributes printed beside the part. **Every
visual difference between two of these drawings is a difference between two
records**: the outline is the brand's colour, the fill is the coating's, the
section is hatched for the material, and the stamp sets every published
attribute verbatim. Nothing is styled from an identifier.

The current generator draws **one drawing per SKU**, from that SKU's own
dimensions, at one true scale per product type, and with no text in it. Those
drawings are not hosted here: the generator builds them as a bundle that a
demo serves itself. See
[Generating a synthetic industrial product catalog](/data-generation/synthetic-industrial-product-catalog/#generated-technical-drawings)
for how they are made and how to build them.

```
/ecommerce-demo-assets/images/industrial/end_mill_square/OST-K663-0001/card.png
/ecommerce-demo-assets/images/industrial/end_mill_square/OST-K663-0001/detail.png
```

## Sections
