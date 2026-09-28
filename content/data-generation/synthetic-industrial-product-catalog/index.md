---
showtoc: true
title: "Generating a synthetic industrial product catalog for search demos"
date: 2026-09-28
description: "A deterministic generator for an industrial-supply catalog (cutting tools and fasteners) with realistic attribute messiness, standards-derived dimensions, and a generated technical drawing for every product line."
slug: synthetic-industrial-product-catalog
---

## Introduction

In two earlier articles I described how I turn open data into demo-ready e-commerce catalogs: [groceries from Open Food Facts](/data-generation/open-food-facts-grocery-demo-data/) and [electronics from Icecat](/data-generation/icecat-electronics-demo-data/). Both work because there is an open source with real products, real images and a licence that is clear enough to build on.

For industrial supply — end mills, drills, taps, socket cap screws, hex bolts, washers — I could not find an equivalent. The real catalogs in this vertical are the distributors' own product data, and none of it can be redistributed as a demo asset. So instead of harvesting a catalog, I wrote a generator for one: [**synthetic-industrial-products**](https://github.com/alexander-marquardt/synthetic-industrial-products).

**Every product it produces is synthetic.** No record describes a real product offered by any retailer, the brands are invented, and no retailer's catalog content is redistributed. What *is* taken from the real world is the shape of the domain: which attribute names the industry uses, which dimension combinations are physically real, how titles are constructed, and how often real records are inconsistent.

## Why generate an industrial catalog at all?

A synthetic catalog is usually the thing you settle for when you cannot get real data, and it tends to make demos less convincing: every field populated, every value well-formed, every title built from the same template. That is not what a real catalog looks like, and it does not exercise a search engine the way a real one does.

Industrial supply has one property in particular that is hard to fake convincingly: **attribute-role ambiguity**. The same dimension token legitimately appears in different roles on the same kind of product. A `3/8"` is the cutting diameter on one end mill and the shank diameter on another. A shopper searching for `3/8 end mill` wants the first and not the second, but full-text search matches both.

On the generated catalog, that is measurable. Of the end mills that carry a `3/8"` value anywhere, 88 have a 3/8" cutting diameter, while 53 carry it only as their shank diameter — a full-text match on the token returns all of them, and only a structured filter on the right attribute separates the two. Demonstrating that a search engine handles this correctly requires a catalog whose dimensions are internally coherent and whose collisions happen at a realistic rate, which is exactly what a naive generator does not give you.

## What it generates

With the default configuration, the generator produces **500 product lines and 4,689 SKUs across 12 product types**, from ten invented brands:

| product type | product lines | SKUs |
| :--- | ---: | ---: |
| `end_mill_square` | 95 | 748 |
| `screw_socket_head` | 60 | 702 |
| `drill_jobber` | 55 | 632 |
| `bolt_hex` | 45 | 471 |
| `end_mill_ball` | 55 | 445 |
| `screw_flat_head` | 35 | 370 |
| `screw_button_head` | 25 | 294 |
| `tap_spiral_point` | 35 | 292 |
| `washer_flat` | 30 | 247 |
| `screw_low_head` | 20 | 190 |
| `hammer_ball_pein` | 20 | 151 |
| `abrasive_flap_disc` | 25 | 147 |

Across those types the catalog publishes **77 distinct attribute names**, with a category path for every product (for example `Milling > End Mills > Square End Mills`).

### Product lines and SKUs

The data model follows how industrial catalogs are actually organised. **A parent is one manufacturer's product line, and its children are the individual purchasable SKUs.** Attributes that are constant across the line (brand, series, material, coating, flute count, end style) live on the parent; the ones that vary (cutting diameter, length of cut, overall length, shank diameter, price, stock) live on each SKU. Lines are never grouped across brands: two manufacturers' tools at the same nominal geometry are different products.

Attributes are key-value pairs, and a measurement carries both its published text and a parsed number in the same entry:

```json
{"name": "Milling Dia.", "value": "3/8\"", "value_num": 0.375}
```

A shopper filters on the published text and ranges over the number, and keeping them on one entry preserves the fact that they are one attribute. The number is parsed *back out of* the published string rather than carried beside it, so the two can never disagree. An attribute that is not a measurement has no `value_num` at all, and neither does a measurement whose value is deliberately malformed.

### Two shapes from one catalog

A single build writes the same generated products in two shapes, so any difference in what they return is a property of the shape rather than of the data:

| file | shape |
| :--- | :--- |
| `nested.jsonl` | one document per product line, with its SKUs and key-value attributes nested |
| `flat.jsonl` | one document per SKU, with attributes denormalised, plus sanitised per-attribute `facets` / `facets_num` fields |
| `images.jsonl` | one row per drawing: its product type, the paths it is published at, and how many products reference it |
| `render.jsonl` | the SKUs in the shape the per-record dimensioned renderer reads |
| `stats.json` | what was generated, measured against the statistics it reproduces |

Elasticsearch mappings for both shapes (`mapping.flat.json`, `mapping.nested.json`) ship alongside them. Here is one SKU from the flat shape, trimmed to its interesting fields:

```json
{
  "sku": "97NR28",
  "product_id": "OST-K663-0001",
  "product_type": "end_mill_square",
  "title": "High Speed Steel Square End Mill, 8mm dia., High Speed Steel, AlTiN,4 Fl",
  "description": "High Speed Steel Square End Mill, 8mm dia., High Speed Steel, AlTiN,4 Fl - 8mm Shank Dia., 32mm Length of Cut, 52mm Overall Length, Osterlund K663",
  "parent_title": "Osterlund K663 -- High Speed Steel Square End Mill",
  "brand": "Osterlund",
  "series": "K663",
  "category_path": ["Milling", "End Mills", "Square End Mills"],
  "dimension_provenance": "generated from the conventional tool series; no standard fixes these values",
  "price_usd": 8.74,
  "stock": 36,
  "image_url": "https://alexmarquardt.com/ecommerce-demo-assets/images/industrial/end_mill_square/OST-K663-0001/card.png",
  "attributes": [
    {"name": "End Mill Style", "value": "Square"},
    {"name": "End Mill Material", "value": "High Speed Steel"},
    {"name": "Finish - Machining", "value": "AlTiN"},
    {"name": "Number of Flutes", "value": "4", "value_num": 4.0},
    {"name": "Milling Dia.", "value": "8mm", "value_num": 0.31496062992125984},
    {"name": "Shank Dia.", "value": "8mm", "value_num": 0.31496062992125984},
    {"name": "Length of Cut", "value": "32mm", "value_num": 1.2598425196850394},
    {"name": "Overall Length", "value": "52mm", "value_num": 2.047244094488189}
  ],
  "facets": {"milling_dia": ["8mm"], "shank_dia": ["8mm"], "finish_machining": ["AlTiN"]},
  "facets_num": {"milling_dia": 0.31496062992125984, "shank_dia": 0.31496062992125984}
}
```

The `facets` object exists because `Milling Dia.` cannot be an Elasticsearch field name (the trailing dot makes it an invalid path), so each attribute gets a sanitised key of its own.

### Why the flat shape is not enough

The flat shape is easy to load, but it has a well-known weakness that the catalog makes visible. In the flat document the `attributes` array is a plain object, so `name` and `value` become two independent multi-valued fields and the pairing between them is lost. On the committed catalog, filtering for *name = `Shank Dia.` AND value = `3/8"`* matches **205** documents, but only **129** of them actually have a 3/8" shank; the other 76 carry a 3/8" that belongs to some other attribute.

That is why the flat shape also carries the per-attribute `facets.*` keys, where the pairing cannot come apart, and why the nested shape exists at all: with nested documents and `reverse_nested`, "how many *products* have this value" becomes answerable.

## Where the realism comes from

### Observed statistics, generated products

The **schema** and the **statistical distributions** are derived from observing publicly archived catalog pages of a real industrial distributor: attribute names, which dimension combinations occur together, how often roles collide, how titles are built, and how often records contradict themselves. Those are facts about the domain. The **products** are generated; they are not real records with the names changed.

That distinction is enforced rather than asserted. The repository ships *hashes* of the reference records' full attribute tuples (never the records themselves), and the test suite checks that no generated product matches any of them. The comparison is over the whole tuple rather than field by field, because agreeing with a published standard on one dimension is not copying — every real `#10` flat head cap screw has the same head diameter — whereas reproducing a complete record would be.

### Dimensions: standards for fasteners, conventional series for cutting tools

The two halves of the catalog get their dimensions differently, and every product line says which:

- **Fasteners** are **standards-derived**. Each line carries the standard its dimensions came from (`ISO 4762`, `ISO 7089`, `DIN 933`, `ASME B18.3` and so on). The values were extracted from open-source CAD fastener libraries — primarily the [FreeCAD Fasteners workbench](https://github.com/shaise/FreeCAD_FastenersWB), with [BOLTS](https://github.com/boltsparts/boltsparts) as corroboration — rather than transcribed by hand, and only the sizes the catalog offers were taken. A size the sources do not carry is absent rather than invented.
- **Cutting tools** are **generated** from the conventional size series. There is no open dimensional source for end mills, so nothing on those lines claims a standard, and the provenance field says so in words (you can see it in the record above).

The asymmetry is deliberate: a cap screw's head is fixed by a published standard and a catalog that disagrees with it is wrong, while an end mill's length of cut is a manufacturer's choice within a conventional range.

### Realistic messiness

Real catalogs are messy, and a search demo on a perfectly clean catalog proves very little. The generator reproduces the defect classes found in the reference data rather than smoothing them away — inconsistent unit formatting within a record, ragged attribute coverage, unlabelled dimension tokens in titles, and occasional internally impossible dimensions. Each rate is reproduced against its own denominator (the records that actually carry the attributes involved), and `sip-generate report` prints what was achieved beside the target:

| measured property | target | achieved |
| :--- | ---: | ---: |
| shank diameter == cutting diameter | 0.6489 | 0.5784 |
| length of cut > overall length | 0.0829 | 0.0842 |
| an angle attribute carries a length unit | 0.0469 | 0.0299 |
| declared measurement system contradicts the value's units | 0.0323 | 0.0301 |
| unit mixing within one record | 0.0222 | 0.0215 |
| title dimension token carries no label | 0.4667 | 0.4600 |
| title dimension token is not the primary dimension | 0.1714 | 0.1736 |
| attributes per record (mean) | 13.12 | 13.69 |

Even the attribute *names* are inconsistent in the way real data is. The measurement-system attribute appears under three different names (`Dimension Type`, `Measurement System` and `System of Measurement`), and the flat shape deliberately keeps them as three separate keys: folding them together at generation time would hide exactly the problem a search layer has to solve.

Titles vary the same way. These are nine SKUs from one product line, a single series of square end mills:

```text
High Speed Steel Square End Mill, 8mm dia., High Speed Steel, AlTiN,4 Fl
High Speed Steel Square End Mill, 10mm D, High Speed Steel, AlTiN, 4 FL
High Speed Steel Square End Mill, 6mm Milling Dia., High Speed Steel, AlTiN, 4 FL
High Speed Steel Square End Mill, 38mm Overall Length, 16mm Cut L, HSS, AlTiN, 4 FL, DBL Sq End
High Speed Steel Square End Mill, 25mm D, High Speed Steel, AlTiN, 4 FL
High Speed Steel Square End Mill, 16mm, HSS, AlTiN, 4 FL, DBL Sq End
Osterlund High Speed Steel Square End Mill, 20mm, High Speed Steel, AlTiN, 4 FL
High Speed Steel Square End Mill, 12mm,High Speed Steel, AlTiN, 4 Flutes
High Speed Steel Square End Mill, 38mm L, 12mm Length of Cut, High Speed Steel, AlTiN, 4 FL
```

The diameter is labelled `dia.`, `D`, `Milling Dia.`, or not at all; `High Speed Steel` is sometimes `HSS`; the flute count is `Fl`, `FL` or `Flutes`; the brand appears in some titles and not others; and two of the titles lead with a length rather than the diameter. All of that is realistic, and all of it is something a query parser has to cope with.

The messiness is bounded by a few rules that keep the catalog usable. Every title names a value that is unique to that SKU within its line, so no two SKUs in a line share a title or a description. The description opens with the title verbatim and then continues with the remaining distinguishing attributes, which is the convention real listings follow: the title tells SKUs apart at a glance, the description while scanning, and the attribute block precisely.

## Generated technical drawings

A demo catalog without images is not a demo catalog, and industrial product photography is exactly the content that cannot be borrowed. So the generator also draws the pictures.

**Every product line has a generated technical drawing, and every SKU in the line shares it** — which is what real industrial catalogs do: a listing of four end mills from one series at four diameters shows the same picture four times. That gives 500 drawings for the 4,689 SKUs, each published at two sizes: a `card` profile (600 × 880) for catalog listings and a `detail` profile (1400 × 1400) for product pages.

![A generated drawing of a square end mill, with its published attributes set beside it](/ecommerce-demo-assets/images/industrial/end_mill_square/OST-K663-0001/detail.png)

There are only twelve shapes, one per product type. What differs between two lines of the same type is the *marking*, and **every visual channel is a function of a published attribute**, never of the product id:

| channel | driven by |
| :--- | :--- |
| outline colour | the brand |
| fill tint | the coating or finish (TiAlN is violet-grey, TiN gold, black oxide dark) |
| section hatch | the material, as engineering drawings already denote it |
| flutes drawn | the published number of flutes |
| flute and thread hand | the cutting or thread direction |
| specification stamp | every published attribute, verbatim |

Rotation, tilt and random variation were considered and rejected: they correspond to no product property, and a reader who sees two tools drawn differently concludes the difference is real. With the drawing driven by the record, that conclusion is correct. The 500 lines produce 497 distinct drawings. The exceptions are three pairs of lines (two of flat washers, one of socket head cap screws) where both lines in a pair have the same brand and publish identical line-level attributes, so drawing each pair identically is the right answer.

Just as important is what the drawings leave out. **No drawing carries a dimension, a callout or a SKU.** One drawing stands behind a whole product line whose sizes typically span a several-fold range, so a drawing that stated a size would be wrong for most of the products it appears against. The sizes live on the record and render beside the image, so the picture cannot contradict the data.

For detail views there is also a second renderer that draws **one record to scale from that record's own attribute values**, with every dimension on the page restating a value the record publishes. It refuses rather than guesses: a record whose dimensions are missing or contradict each other is not drawn to scale, because a defaulted dimension would produce a picture that disagrees with its own record.

### Publishing the drawings

The drawings are hosted on this site, under [E-commerce Demo Assets](/ecommerce-demo-assets/images/industrial/), where every product type has a browsable page of its lines' drawings. The URL of each drawing is derived from the product line it belongs to (`industrial/<product type>/<product line>/card.png`), and every record carries its `image_url` and `image_detail_url`.

Because a regeneration mints new product lines — and therefore new image URLs — publishing the drawings is part of regenerating the catalog rather than a separate errand. The build writes `images.jsonl`, a manifest of every image and the path it must be published at; the importer on the hosting side reads that manifest instead of re-deriving the paths; and a CI gate on the generator compares the complete set of files the manifest names against the files actually published, so a catalog whose images are not live yet cannot land. It compares the whole set rather than sampling it, because a sample of one image per product type can look healthy while almost every other URL is dead.

## Using it

The generator is a Python package managed with [uv](https://docs.astral.sh/uv/). A build is deterministic: one seed produces one catalog, byte for byte.

```sh
git clone https://github.com/alexander-marquardt/synthetic-industrial-products.git
cd synthetic-industrial-products
uv sync
uv run sip-generate build --out out/catalog   # writes the files above
uv run sip-generate report                    # the measured-vs-target table only
```

Everything is parameterised, because the point of a synthetic catalog is to be dialled until something breaks:

```sh
uv run sip-generate build --lines 900 --skus 6 24    # more, wider product lines
uv run sip-generate build --sparsity 0.4             # raggeder attribute coverage
uv run sip-generate build --defects 0.0              # a catalog with no contradictions
uv run sip-generate build --seed 7                   # a different catalog
```

`--image-base-url` changes the host the image URLs point at, and the drawings themselves are rendered with:

```sh
uv run sip-render generics --out out                              # the twelve shapes, unmarked
uv run python scripts/render_catalog.py out/catalog --out out/images   # every line, both profiles
```

If you just want the data, you do not need to run anything: the default build is committed to the repository under `golden-catalog/`, as plain NDJSON so that a change to the generator shows up as a readable diff. Loading the flat shape into Elasticsearch takes the committed mapping and a bulk request:

```sh
ES=http://localhost:9200
curl -X PUT "$ES/industrial-products" -H 'Content-Type: application/json' \
  --data-binary @golden-catalog/mapping.flat.json

jq -c '{index: {_id: .sku}}, .' golden-catalog/flat.jsonl > bulk.ndjson
curl -X POST "$ES/industrial-products/_bulk?refresh=true" \
  -H 'Content-Type: application/x-ndjson' --data-binary @bulk.ndjson
```

For a larger generated catalog, split `bulk.ndjson` into chunks (for example with `split -l 2000`) so that no single request gets too large.

The repository also contains a verification script that loads both shapes into a local test cluster and checks that every number Elasticsearch returns — facet counts, range filters, the `3/8"` shank-versus-cutting-diameter case — equals one computed independently in Python from the generated objects, and a customization package for PRISM, the search governance layer from the [e-commerce videos](/#ecommerce-videos) on my homepage.

## What's next

The current catalog is deliberately concentrated: twelve product types, most of them cutting tools and socket screws. I am planning to broaden it toward roughly 10,000 products spread over many more product types across the category tree — every one of them still with a generated drawing — and I will update this article when that lands.

## Conclusion

Open Food Facts and Icecat give me real products for groceries and electronics. For industrial supply there is no open equivalent, so the next best thing is a generator that is honest about what it is: synthetic products, whose schema, distributions, messiness and even pictures are all derived from — and checked against — how real catalogs in the domain behave. The result is a catalog that is safe to share, reproducible from a seed, and awkward in all the ways that make a search demo worth watching.
