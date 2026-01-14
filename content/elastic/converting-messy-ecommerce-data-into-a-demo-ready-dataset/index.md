---
title: "Demo-grade e-commerce datasets: Clean and useable grocery and electronics datasets"
date: 2026-01-13
description: "Turn messy product data into clean, image-rich NDJSON for e-commerce search demos and relevance work."
slug: clean-ndjson-ecommerce-demo-data
---

## Introduction

If you want to demo e-commerce search, you need good data: titles that look real, images that load, categories and attributes that facet cleanly, and enough product variety that a query rewriter or a re-ranker actually has room to show impact. 

Because it is difficult to find good, free, and open demo data sets, many teams get stuck using a small dataset, or a synthetic toy catalog, or whatever was easiest to download. This results in unrealistic demos, and customers end up confused as to why the amazing demo experience isn't reproduceable on production system.

For work that I am doing on a query rewriter I need a good and large dataset with the following characteristics:

1. **A realistic product catalog** that is large enough and rich enough to demo modern e-commerce search (including images).
2. **A clean representation** of that catalog that is easy to ingest into a search engine and easy to iterate on.

To get there, I built two small repositories that take open sources and produce “demo-grade” NDJSON: one based on [Open Food Facts](https://es.openfoodfacts.org/) which results in over 100K useable and clean grocery products, and one based on [Open Icecat](https://icecat.biz/) which results in over 1 million useable and clean compuetr and elecronics products. The value of these scripts is that they take the type of data that normally comes in awkward formats (huge nested JSON/XML, inconsistent field names, unclear image handling) and convert it into a consistent, search-ready document format.

- Icecat harvester: https://github.com/alexander-marquardt/icecat-harvester/
- Open Food Facts extractor: https://github.com/alexander-marquardt/open-food-facts-ndjson-extractor

## Why NDJSON is the point

Search systems want documents. They want one document per product, flat enough to map and query, but rich enough to facet, filter, and display.

Many “product datasets” technically contain what you need, but the structure is hostile to iteration. A product might have hundreds of fields, nested sub-documents, language variants scattered across keys, and images represented as metadata that still requires custom URL construction. You can absolutely write the glue once, but then you end up rewriting it every time you switch data sources or every time your demo needs one additional field.

NDJSON is boring in exactly the right way: one JSON object per line, streamable, greppable, and trivial to bulk ingest. The end-state I wanted for both sources was the same: a clean, stable schema that a search engine can ingest in minutes.

## Dataset #1: Open Food Facts as a demo catalog (with images)

Open Food Facts is not an “e-commerce” dataset in the Amazon sense. It is a product database built for transparency: ingredients, allergens, nutrition, and label-derived metadata. The reason it works so well for demos is that it still behaves like a real product catalog: it has product names, categories, and images. Importantly, its data reuse posture is explicit and documented (ODbL for the database; CC BY-SA for images). That clarity matters when you intend to show a dataset to customers.

The raw Open Food Facts export is a huge JSONL file with a lot of structure. The extractor repository turns it into clean NDJSON that is immediately indexable. It also computes image URLs based on the official image URL scheme, and it can apply quality gates such as “English titles/descriptions” and “must have a front image.”

Repo: https://github.com/alexander-marquardt/open-food-facts-ndjson-extractor

The output schema is intentionally practical. It includes:

### Schema Overview

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | string | GTIN-13 barcode (padded). |
| `title` | string | Product name (English). |
| `brand` | string | Manufacturer or brand name. |
| `description` | string | Synthesized description (Title + Ingredients + Key Specs). |
| `price` | float | Synthetic, deterministic price for e-commerce simulation. |
| `currency` | string | Currency code (default: EUR). |
| `image_url` | string | Computed primary product image URL. |
| `categories` | list | Cleaned list of category tags. |
| `attrs` | object | **Flattened Dictionary** of key-value attributes (e.g., Nutri-Score, Energy). |
| `attr_keys` | list | List of all keys available in `attrs` for faceting. |
| `dietary_restrictions` | list | Extracted dietary tags (e.g., vegan, vegetarian). |

### After: Cleaned NDJSON for Search Example

The output is over 100K clean, flat JSON objects, that are ready to be indexed into a search engine like Elasticsearch or OpenSearch.

```json
{
  "id": "0008127000019",
  "title": "Extra virgin olive oil",
  "brand": "Athena Imports",
  "description": "Extra virgin olive oil\n\nExtra virgin olive oil\n\n\nKey Specifications:\n- **Category**: Plant based foods and beverages\n- **Serving size**: 15 ml\n- **Nutri-Score**: B\n- **NOVA group**: 2\n- **Eco-Score**: E\n- **Dietary**: vegan, vegetarian\n- **Ingredients analysis**: palm-oil-free, vegan, vegetarian\n- **Energy (kcal/100g)**: 800 kcal\n- **Fat (g/100g)**: 93.3 g\n- **Saturated fat (g/100g)**: 13.3 g\n- **Sugars (g/100g)**: 0 g\n- **Salt (g/100g)**: 0 g\n- **Protein (g/100g)**: 0 g\n- **Countries**: United States",
  "image_url": "https://images.openfoodfacts.org/images/products/000/812/700/0019/front_en.5.400.jpg",
  "price": 0.49,
  "currency": "EUR",
  "categories": [
    "Plant based foods and beverages",
    "Plant based foods",
    "Fats"
  ],
  "attrs": {
    "Serving size": "15 ml",
    "Nutri-Score": "B",
    "NOVA group": "2",
    "Eco-Score": "E",
    "Ingredients analysis": "palm-oil-free, vegan, vegetarian",
    "Countries": "United States",
    "Category": "Plant based foods and beverages",
    "Energy (kcal/100g)": "800 kcal",
    "Fat (g/100g)": "93.3 g",
    "Saturated fat (g/100g)": "13.3 g",
    "Sugars (g/100g)": "0 g",
    "Salt (g/100g)": "0 g",
    "Protein (g/100g)": "0 g",
    "Dietary restrictions": "vegan, vegetarian",
    "Price source": "estimated_unit_model",
    "Pricing bucket": "oils_fats",
    "Estimated unit price": "11.59 EUR/l (15ml, bucket=oils_fats, scale=1.21, ratio=0.15)"
  },
  "attr_keys": [
    "Category",
    "Countries",
    "Dietary",
    "Eco-Score",
    "Energy (kcal/100g)",
    "Estimated unit price",
    "Fat (g/100g)",
    "Ingredients analysis",
    "NOVA group",
    "Nutri-Score",
    "Price source",
    "Pricing bucket",
    "Protein (g/100g)",
    "Salt (g/100g)",
    "Saturated fat (g/100g)",
    "Serving size",
    "Sugars (g/100g)"
  ],
  "dietary_restrictions": [
    "vegan",
    "vegetarian"
  ]
}
```

### Benefits

The key is that once the data is in this shape, you can iterate on search logic quickly. Query rewriting rules, category routing, facet behavior, synonyms, typo handling, attribute extraction — all of it becomes easier when the data is already clean.

### How the data looks

Below is an example of how the cleaned Open Food Facts data looks in a simple ecommerce frontend.

![Demo screenshot](images/cleaned-food-data.png)

## Dataset #2: Icecat for electronics-style product catalogs

Open Food Facts is excellent for food/CPG. But many demos benefit from an electronics-style catalog with spec-rich attributes and product-type variety. That’s where Icecat is useful.

Icecat is typically consumed via XML interfaces and nested structures that cannot be indexed directly into Elasticsearch. The Icecat harvester repo is designed as an ETL pipeline where downloading and parsing are separate steps. That separation matters: you can download once, iterate on schema transformation many times, and regenerate clean NDJSON without re-downloading everything.

Repo: https://github.com/alexander-marquardt/icecat-harvester/

### Schema Overview

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | string | Unique Icecat product identifier. |
| `title` | string | Full product name and marketing title. |
| `brand` | string | Manufacturer name (e.g., Lenovo, HP). |
| `description` | string | Cleaned text description (HTML tags removed). |
| `price` | float | Estimated/Heuristic price in EUR. |
| `image_url` | string | Primary high-resolution product image URL. |
| `categories` | list | List of category names assigned to the product. |
| `attrs` | object | **Flattened Dictionary** of technical specifications. |
| `attr_keys` | list | List of all keys available in `attrs` (used for search facets). |

### Example Record

```json
{
  "id": "91778569",
  "title": "Lenovo Legion 5 15ARH05H AMD Ryzen™ 7 4800H Laptop...",
  "brand": "Lenovo",
  "description": "Minimal meets mighty... Thermally tuned via Legion Coldfront 2.0.",
  "price": 865.33,
  "currency": "EUR",
  "image_url": "https://images.icecat.biz/img/gallery_mediums/79117985_5269963235.jpg",
  "categories": ["Laptops"],
  "attrs": {
    "Processor family": "AMD Ryzen™ 7",
    "Internal memory": "16 GB",
    "Weight": "2.46 kg"
  },
  "attr_keys": ["Processor family", "Internal memory", "Weight"]
}
```

### How the data looks

Below is an example of how the cleaned icecat data looks in a simple ecommerce frontend.

![Demo screenshot](images/cleaned-electronics-data.png)

## One schema, two sources

The goal is that a loader or indexing pipeline can ingest both Icecat and Open Food Facts with the same code path. That’s why both repositories converge on a similar NDJSON structure:

- stable top-level fields (`id`, `title`, `brand`, `description`, `image_url`, `price`, `currency`, `categories`)
- an attribute map (`attrs`) plus a list of keys (`attr_keys`) that is easy to turn into facets
- deterministic output for reproducibility

When the schema contract is consistent, you can swap catalogs without rewriting the ingestion or the demo UI.

## Where WANDS fits: evaluation, not demos

It’s worth calling out one dataset that I do consider extremely valuable: [WANDS](https://github.com/wayfair/WANDS) (Wayfair ANnotation Dataset).

WANDS includes query-product relevance judgments. That makes it excellent for benchmarking relevance changes and checking whether something you did actually improved ranking quality. The dataset is also explicitly MIT licensed.

- WANDS repo: https://github.com/wayfair/WANDS
- Paper: https://easychair.org/publications/preprint/j2D4/download

However, WANDS is comparatively small, and it is not ideal as a primary “demo catalog.” The biggest practical issue for demos is that a demo UI benefits enormously from images, and WANDS is not structured as an image-forward catalog. For my purposes, WANDS is something I want in the toolbox for evaluation, while the demo catalog comes from OFF and Icecat.

In other words: WANDS allows you to quantitatively evaluate quality of search results, while Open Food Facts/Icecat data allows you to create realistic demos and to evaluate results qualitatively.

## Other datasets we considered (and why we did not choose them)

There are many attractive datasets in the research ecosystem, but many of them come with constraints that make them awkward for customer-facing demos or reusable internal assets.

### Amazon-derived datasets (UCSD / McAuley Lab)

The UCSD / McAuley Lab Amazon datasets are impressive: reviews, metadata, sometimes images, large scale. For demos, they look great on paper.

The problem is not technical quality. The problem is posture: the underlying content originates from Amazon, and many releases are framed as academic research resources. In addition, the Amazon Reviews 2023 ecosystem is frequently referenced with non-commercial research restrictions in derivative distributions.

- Amazon Reviews 2023 landing page: https://amazon-reviews-2023.github.io/
- UCSD Amazon review data: https://jmcauley.ucsd.edu/data/amazon/
- Example derivative noting “Academic, non-commercial research use only”: https://huggingface.co/datasets/bagadbilla/amazon-reviews-2023-trimmed

If you are building a reusable demo asset, there may be legal obstacles to using this data.

### SIGIR eCom / Coveo data challenge datasets

These datasets are excellent for research, especially session-based behavior (queries, clicks, add-to-cart, etc.). They are also often explicitly described as being made available for research purposes, with access gated by terms.

- SIGIR eCom 2021 / Coveo challenge repo: https://github.com/coveooss/SIGIR-ecom-data-challenge

If you’re doing academic work or internal R&D, they can be great. If you’re building a demo catalog that you want to use broadly in customer conversations, the terms can complicate things.

### Kaggle competition datasets (H&M example)

Kaggle competitions are a common source of “easy to download” datasets that look demo-friendly. The issue is that many competitions explicitly restrict use to non-commercial purposes.

- H&M competition rules (non-commercial clause): https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules

Again: excellent for learning, but not the cleanest foundation for customer-facing demos.

### TREC Product Search and “Amazon thumbnail” corpora

Some product search datasets include images and evaluation infrastructure, but the provenance matters. For example, the TREC 2023 Product Search track overview explicitly discusses product images extracted from Amazon thumbnails and joined using ASINs.

- TREC 2023 Product Search overview: https://arxiv.org/pdf/2311.07861

This may be perfectly fine for research benchmarking, but it reintroduces the same “marketplace-derived content” concern when you want a demo catalog with a clean commercial posture.

## Conclusion

If you want to build and demo e-commerce search, the blocker is rarely your search engine. The blocker is usually the dataset. Most people accept that and operate with a small catalog because they believe that getting good data is difficult. The point of these two repositories is to ease that burden.

Open Food Facts and Icecat are not magical. They are just two sources that (a) contain the kinds of fields demos need, including images and metadata, and (b) have licensing frameworks that are clear enough to build on without feeling like you’re stepping into a gray area. The real work — and the real value — is in turning raw, awkward source formats into clean, stable NDJSON that is easy to index, easy to query, and easy to use in demos. Not more, not less.

If you’re doing relevance evaluation, WANDS is still in the picture. It’s a different tool for a different job. But for demo catalogs that look and feel real, Icecat and Open Food Facts are the two foundations I’m using today.