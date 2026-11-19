---
showtoc: true
title: "The catalog writes the merchandising rules: replacing hand-written search rules with vocabularies"
date: 2026-11-19
draft: true
slug: catalog-writes-the-merchandising-rules
tags: ["elasticsearch", "ecommerce", "search-relevance", "merchandising", "percolator"]
description: "Every e-commerce search team keeps a long list of hand-written rules: steak means the Meat category, cheap means a price cap, m8 means a thread size. This article shows how vocabularies extracted from the catalog, a grammar for typed shapes, and a short list of merchandiser exceptions take over most of that list."
---

## Introduction

Every e-commerce search team I have worked with keeps a list of hand-written rules. A search for `steak` should show beef steaks, not steak knives. `cheap` should cap the price. `Nike` should filter to the brand. `m8 bolts` should filter on the thread size. A store has thousands of these, and a merchandiser writes, tests and maintains each one by hand. When the catalog changes, the rules drift: a new brand has no rule, a renamed category breaks one, and nobody notices until a shopper gets an empty page.

This article is about a different way to get the same result. Most of what those rules encode is already in the catalog: its category names, its brands, its attribute values and its units. If the search layer reads that data and uses it to interpret the query, then the catalog writes most of the rules, and the merchandiser handles only the exceptions.

The examples come from PRISM, the governed e-commerce search layer described in the [Elasticsearch Labs series](#further-reading), and run on the demo catalogs described on this site: [the synthetic retail and industrial catalog](/data-generation/synthetic-retail-and-industrial-catalog/), [the grocery data from Open Food Facts](/data-generation/open-food-facts-grocery-demo-data/) and [the electronics data from Icecat](/data-generation/icecat-electronics-demo-data/). The Labs series covers the governance model, the control plane and how policies are matched with the percolator. This article does not repeat that material. It covers the part those articles leave out: where the rules come from.

## The rules a merchandiser writes today

Earlier articles on this site describe the hand-built way to make search relevant: [combining stemmers and synonyms](/elastic/combining-elasticsearch-stemmers-and-synonyms-to-improve-search-relevance/), [boolean queries that reward the right matches](/elastic/using-boolean-queries-to-improve-search-relevancy-in-elasticsearch/), [ranking by profit and popularity](/elastic/ranking-by-profit-and-popularity-in-elasticsearch/) and [personalizing results from purchase history](/elastic/personalizing-search-in-elasticsearch-without-ml-post-processing/). Each technique works. Each also needs a person to decide, word by word, what the shopper meant.

A governed search layer makes those decisions explicit. In PRISM, they are **policies**: stored queries that match the shopper's text and change how the search runs, for example by filtering to a category, capping a price or boosting a brand. [The percolator article in the Labs series](https://www.elastic.co/search-labs/blog/elasticsearch-percolator-search-governance) shows one being written: a merchandiser authors a policy for the phrase `oranges` that filters to the Fruits category. That is a good rule, and it is still a rule per word. A catalog with thousands of categories and tens of thousands of brands needs thousands of them.

The demo's own policy set still contains rules of that kind. Here is the trigger of its `cheap olive oil` policy:

```yaml
trigger:
  kind: any_of
  options:
    - kind: seq
      seq:
        - { kind: text, text: cheap }
        - { kind: text, text: olive }
        - { kind: text, text: oil }
    - kind: seq
      seq:
        - { kind: text, text: inexpensive }
        - { kind: text, text: olive }
        - { kind: text, text: oil }
    # ... and the hyphenated and joined spellings of both
```

When it fires, it filters to the **Olive oils** category and caps the price at $10. It works for exactly one phrase. `cheap rapeseed oil` needs another policy, and so does `cheap pasta`. Two different facts are mixed together in it. **Olive oil is a category** is a fact about the catalog. **Cheap means under $10 here** is a decision about the store. Only the second one needs a merchandiser.

## From a rule per word to a rule per shape

The change that removes most of the hand work is small to describe. A policy's trigger does not have to name a word. It can name a **marker**, a placeholder that stands for every value of a vocabulary or every string of a given shape:

- `${BRAND}` stands for any brand the catalog carries.
- `${CATEGORY}` stands for any word that names a category.
- `${CURRENCY}` stands for an amount of money, such as `$50` or `5 dollars`.
- `${NUMBER}` and a fraction marker stand for `20`, `1,000` and `1/2`.
- A unit vocabulary such as `${UNIT_LENGTH}` stands for `mm`, `in`, `inch` and `"`.

When a shopper searches, the search layer finds the spans of the query that belong to a vocabulary and puts the marker in their place before the policies are matched. A single policy whose trigger reads `${BRAND}` and whose action filters on the brand that was typed then does the work of one rule per brand. On the grocery demo, the brand vocabulary holds **35,560** values, all extracted from the catalog's brand field. Written as one rule per brand, that is tens of thousands of rules. With a marker, it is one policy.

The question then becomes where the vocabularies come from. In PRISM, the answer is the catalog itself.

## 1. Vocabularies are extracted from the catalog

A vocabulary is declared by naming the catalog field it reads, for example `brand`, the category tree or a product attribute. A data refresh (`populate-vocab`) reads the distinct values of that field and writes them into one curation index, one document per word, each with its state (recognized or removed) and the time it was last changed. The Engine loads the recognized words into memory and checks each query against them there, so recognizing a word costs no extra Elasticsearch request on the search path.

The category tree becomes a vocabulary in the same way. Each category's own name is a trigger word for that category. `Steak` is a word on a row of the Meat department, so the search reads `steak` as the food and filters the best-matching results to that category. Nobody wrote a rule that says "steak means beef". Steak knives are not in a category the word names, so the filter leaves them out.

A word can be on more than one row, and the search then filters to all of them at once. On the combined retail and industrial demo, `nuts` is a category under Hardware (Fasteners, Nuts) and under Food & drink (Biscuits & snacks, Nuts & popcorn). A search for `nuts` filters to both categories in one filter and opens with a bag of mixed nuts. `hex nuts` keeps the same filter, and the other word in the query ranks a brass hex nut first. The catalog supplied both readings. The ranking decided between them.

## 2. A grammar reads typed shapes

Some of what shoppers type is not a word from any list. `m8 x 20`, `2 in long`, `1/2 inch` and `under $50` are **shapes**: a number, maybe a fraction, maybe a unit, maybe a currency sign, in an order that means something. A keyword rule cannot cover them, because the values are open-ended. No one writes a rule for every length.

PRISM reads these shapes with a small grammar made of markers:

- **Pattern markers** recognize numbers, fractions and amounts of money. They honour the store's number format, so `1,000` is one number, and they accept spaced forms such as `$ 5`, and spelled ones such as `5 dollars` or `4 euro` once the store lists those words.
- **Unit vocabularies** hold the spellings of each unit. `inch`, `in` and `"` all mean the inch; `mm` means the millimetre. Each spelling belongs to a unit code, and each code has an exact conversion factor, written as a fraction rather than a float, so `1/2 inch` converts to exactly 12.7 mm.
- **One policy per shape** combines them. Its trigger accepts either notation (`12.7 mm` or `1/2"`). Its action becomes a range filter on the attribute, in the unit the catalog stores, whatever unit the shopper typed.

The unit spellings are also catalog data. They are collected from the values the catalog carries and curated in the same Data Management page as the brands, so a store that writes `in.` in its titles can add that spelling without a code change.

The policies that read these shapes are still written by hand, once each: one for a size, one for a price ceiling, one for a dimension pair. What changes is the count. A rule per value becomes a rule per shape, and a store has a handful of shapes, not thousands.

## 3. The merchandiser handles the exceptions

Catalog data is noisy, and some decisions are not in the data at all. So the merchandiser still has three jobs, but each is small, and each is done in PRISM Studio with the result visible at once.

**Overriding a word.** A catalog's `brand` field holds real brands next to product types someone typed there by mistake: `Coca-Cola` and `Nestlé` next to `Chocolate` and `Soy`. Without curation, `chocolate` would be read as a brand. In Data Management, every value is in one of three states:

- **Recognized:** the search treats it as a member of the vocabulary.
- **Removed:** the search ignores it as a vocabulary word.
- **New:** a value the catalog gained since the last review, which needs a decision.

Removing `Chocolate` from the brands takes one click. It needs no reindex and no catalog edit.

**Adding a synonym.** A shopper who types `cup` usually wants mugs too. The merchandiser adds `cup` to the Mugs row. A search that selects that row then searches all of the row's words, so `cup` also finds products named `mug`, and a product that says `cup` is still boosted. The direction is part of the decision. Putting `aqua` on the Blue row makes `aqua` find blue products, but `blue` does not find aqua ones. For a two-way synonym, the merchandiser adds each word to the other's row.

**Deciding what cheap means.** Cheap is a business decision, not a catalog fact. It is written once, as a policy that reads `cheap` and caps the price, and it combines with whatever the vocabulary reads in the rest of the query. With the category reading handled by the vocabulary, that policy no longer needs to name olive oil.

Before saving a word, the merchandiser can preview a search with it. A saved word is rebuilt straight away on the engine that saved it, so the next search reads it, and other engines pick it up at their next check for changes.

## 4. It stays in sync

Because the rules are not written per value, the catalog and the search do not drift apart. When the catalog gains a category, its name is a word in the category vocabulary at the next data refresh. When it gains a brand, the brand appears in Data Management's review queue at the next data refresh.

One honest detail: after a vocabulary is first filled, PRISM does not trust new values blindly. The first fill of an empty vocabulary recognizes every value the catalog carries. After that, a value the catalog gains waits as **New** until a merchandiser recognizes it, because the same noise that put `Chocolate` in the brand field can arrive with the next import. Meanwhile, products carrying the new value are still found by ordinary text search. Recognizing it is one click. Nobody writes a rule.

## 5. It is explainable

A rule list that grows by hand is hard to debug: when a search goes wrong, someone has to find which of thousands of rules fired. Here every filter and boost names where it came from. With debug on, the search response names, for each reading of the query:

- the vocabulary and the row it read;
- the word as the row holds it;
- whether the word is the row's own name (a trigger word) or a word a merchandiser added (a synonym);
- the policy that turned it into a filter or a boost.

So "why did `nuts` show me snacks?" has an answer that points at a row in Data Management, not at a guess.

## What the catalog does not write

The claim is "most of the rules", not "all of them", and the rest is worth naming:

- **Business decisions stay with the merchandiser:** what cheap means, a seasonal promotion, a brand the store is pushing, a sponsored result. These are policies, and they should be. [The Labs article on margin and popularity boosting](https://www.elastic.co/search-labs/blog/ecommerce-search-optimization-query-governed) covers that side.
- **Noisy data still needs a review:** the curation states exist because a catalog field is not a clean vocabulary.
- **Each shape still needs one policy:** a size, a price ceiling or a colour followed by a category is written once, then applies to every value.

What disappears is the long tail: the rule per category word, per brand and per unit spelling, and the maintenance of those rules every time the catalog changes.

## Four examples

Screenshots of each example, before and after, follow in a later revision of this draft.

### `steak`

- **Before:** a rule that maps `steak` to the Meat category, plus a negative rule so that steak knives do not rank first.
- **From the catalog:** `steak` is a word on a Meat category row, so the search filters the best matches to that category. No Kitchen category carries the word.
- **Left for the merchandiser:** nothing.

### `cheap olive oil`

- **Before:** the policy shown above, one per product type, each with its own price cap.
- **From the catalog:** `olive oil` reads as the Olive oils category.
- **Left for the merchandiser:** one decision, that cheap means under $10 in this store, written once for every category.

### `cup`

- **Before:** a synonym rule, `cup` ⇒ `cup, mug`, in a synonym set that someone maintains next to the index.
- **From the catalog:** the Mugs category and its products.
- **Left for the merchandiser:** adding `cup` to the Mugs row in Data Management, previewed before it is saved and live at once.

### `m8 x 20 socket cap screw`

- **Before:** a rule per thread size and length, or none at all, which leaves a text match on `m8` and `20` that also matches part numbers and pack counts.
- **From the catalog:** `socket cap screw` reads as a category. The grammar reads `m8` as a metric thread size and `20` as a length in millimetres, and turns each into a filter on the attribute the catalog stores.
- **Left for the merchandiser:** nothing for this query. The policy for the shape `<thread> x <length>` is written once and serves every size.

## How much of the work is gone

**Figures to come in a later revision of this draft.** The demo query sets will be run twice on the demo catalogs: with the vocabularies and the grammar only, and with the hand-authored policies as well. Two numbers will go here:

- the share of queries interpreted correctly with no hand-written policy, which is the headline: "N% of the intent a merchandiser used to encode by hand now comes from the catalog";
- the number of rules a rule-per-query setup needs for the same query set, against the number of overrides PRISM needed.

## Further reading

The PRISM series on Elasticsearch Labs:

1. [Why ecommerce search needs governance & how it improves retrieval](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-improve-retrieval)
2. [Accelerating merchandising improvements with a governed control plane](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-zero-deploy)
3. [Building a control plane to govern ecommerce search](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-control-plane-architecture)
4. [Elasticsearch percolator for ecommerce search governance: translating ambiguous queries into controlled retrieval strategies](https://www.elastic.co/search-labs/blog/elasticsearch-percolator-search-governance)
5. [Multi-tier search with Elastic for ecommerce search governance: fixing poor recall](https://www.elastic.co/search-labs/blog/multi-tier-search-ecommerce-governance)
6. [Personalizing ecommerce search: integrating purchase history and user cohorts](https://www.elastic.co/search-labs/blog/elasticsearch-personalized-search-governed-ecommerce)
7. [Ecommerce search optimization using margin and popularity boosting in Elasticsearch](https://www.elastic.co/search-labs/blog/ecommerce-search-optimization-query-governed)
8. [Agentic AI search with deterministic guardrails in Elasticsearch for safe query execution](https://www.elastic.co/search-labs/blog/agentic-ai-search-deterministic-guardrail-query-execution)

## Draft notes (remove before publishing)

**Points the Labs articles already make, which this draft links rather than restates:**

- Governance is the decision layer upstream of retrieval: it classifies intent, applies constraints and routes to lexical, semantic or hybrid retrieval, producing a governed retrieval plan. ([1](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-improve-retrieval))
- Hard-coded if-then statements and regexes in application code do not scale; "the bottleneck isn't the engine; it's the operating model". ([1](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-improve-retrieval))
- Head and tail query examples: `oranges`, `air max 270`, `iPhone 15 Pro`, `fruit high in vitamin C under $4`. ([1](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-improve-retrieval))
- Policies live in their own index and are matched with the percolator. ([3](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-control-plane-architecture))
- Matched policies apply as a cascade in priority order. Conflicts resolve per field as a hard filter or a soft boost (override, restrict, merge), and consumed phrases are tracked. ([3](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-control-plane-architecture))
- Cheap chocolate (a $2 cap) and Christmas chocolate (a $7 cap, advent calendars boosted) as policy examples. ([3](https://www.elastic.co/search-labs/blog/ecommerce-search-governance-control-plane-architecture))
- A merchandiser authors a policy in Studio: one literal phrase per policy, such as `oranges` filtered to Fruits, wrapped in start and end tokens so `orange marmalade` does not fire it. ([4](https://www.elastic.co/search-labs/blog/elasticsearch-percolator-search-governance))
- The policy index mapping (`percolator`, `query`, `query.stemmed`, `rule_type`, `rule_args`, `priority`, `enabled`), and `olive oil` matched on the stemmed field. ([4](https://www.elastic.co/search-labs/blog/elasticsearch-percolator-search-governance))
- Variable patterns, such as `under $4` containing a currency value, are mentioned as possible but not shown. ([4](https://www.elastic.co/search-labs/blog/elasticsearch-percolator-search-governance))

None of the three covers vocabularies extracted from the catalog, brand recognition, unit parsing or markers such as `${BRAND}`. That is this article's own ground.

**To verify on the demo before publishing:**

- `steak` with policies off filters to a Meat category row, and which row carries the word.
- `olive oil` with policies off reads as the Olive oils category, and whether the served demo has a generic `cheap` policy or only the per-phrase one shown above.
- `m8 x 20 socket cap screw` reads the thread size and the length as described, on the industrial persona.
- The `cup` synonym is on the Mugs row of the persona the screenshot uses.

**Open points for the author:**

- What can be said publicly about PRISM, and when. The article stays `draft: true` until that is decided.
- Public brands only, no customer names. The brands named here (Nike, Coca-Cola, Nestlé) are public.
