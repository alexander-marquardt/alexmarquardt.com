---
title: "E-commerce Demo Assets"
description: "Public image assets for e-commerce search demos and testing."
url: "ecommerce-demo-assets"
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
/ecommerce-demo-assets/images/industrial/end_mill_square/98WF97.png
```

The industrial path carries a product type because the catalog's records
reference each other's drawings: roughly three records in four point at an image
filed under some other product's SKU, and the reuse crosses product types. The
directory names the product **drawn**, never the product referencing it.

## Sections
