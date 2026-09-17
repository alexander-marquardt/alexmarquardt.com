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
/ecommerce-demo-assets/images/industrial/<product-type>/<image-ref>.png
```

For example:

```
/ecommerce-demo-assets/images/electronics/apple-iphone-001.png
```

Every listing below is read from the directory it describes when the site is
built, so what you see there is what is actually hosted.

The industrial path carries a product type because products in the same family
share one drawing, as they do in a real supplier's catalog — several sizes of
the same end mill are listed against the same picture. So a catalog record does
not have an image of its own to point at: many records resolve to the same URL,
and the directory names the product type **drawn** rather than any one product
referencing it.

## Sections
