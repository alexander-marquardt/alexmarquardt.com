---
title: "How to tune Elasticsearch for aggregation performance"
date: 2018-10-02
slug: how-to-tune-elasticsearch-for-aggregation-performance
aliases: 
  - /how-to-tune-elasticsearch-for-aggregation-performance
---

October 2, 2018

# Introduction

By default, Elasticsearch is tuned for the best trade-off between write performance and query performance for the majority of use cases. In this blog posting we cover some parameters that can be configured to improve query-time aggregation performance, with _some_ of these improvements coming at _the expense of write performance._ 

Note that this blog posting does not present anything that is not already documented in other locations. The goal here is to pull together relevant information into a small and digestible posting that provides a few pointers on how to improve slow Elasticsearch aggregations.

# A description of the refresh interval

In this section we give an overview of the [refresh interval](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-for-indexing-speed.html#_increase_the_refresh_interval), which is useful for understanding subsequent sections of this blog.

As documents are inserted into Elasticsearch, they are written into a buffer and then periodically flushed from that buffer into [segments](https://www.elastic.co/guide/en/elasticsearch/guide/current/dynamic-indices.html#dynamic-indices) when a _refresh_ occurs. By default refreshes occur every 1 second, which is known as the refresh\_interval. Newly inserted documents are not searchable until they have been flushed into segments.

In the background, small segments are merged into larger segments, and those larger segments are merged into even larger segments, and so on.  Therefore, by enabling frequent refreshes, Elasticsearch needs to do more background work merging small segments than it would need to do with less frequent refreshes which would create larger segments to start with.

While frequent refreshes are necessary if near-real-time search functionality is required for newly inserted data, they may not be necessary in other cases. If an application can wait longer for recent data to appear in search results, then the refresh interval should be increased in order to improve the efficiency of data ingestion, which in-turn should free up resources to help query performance.

# Enable eager global ordinals to improve the performance of high-cardinality terms aggregations

**May 9, 2019 update**: A more in-depth explanation of terms aggregations on high-cardinality fields has now been published: https://www.elastic.co/blog/improving-the-performance-of-high-cardinality-terms-aggregations-in-elasticsearch.

The performance of terms aggregations on high-cardinality fields (fields with thousands or millions of possible unique values) may become slow and unpredictable in-part because by default global ordinals are _lazily_ built on the first aggregation that occurs since the previous refresh [as described here](https://github.com/elastic/elasticsearch/issues/19780).

Building [global ordinals eagerly](https://www.elastic.co/guide/en/elasticsearch/reference/master/eager-global-ordinals.html) should improve such aggregations and make response times more consistent, as the related data structure will be created when segments are refreshed, as opposed to the first query after each refresh.

Note that if global ordinals are eagerly built, this will impact write performance because new global ordinals will be created on every refresh. To minimize the additional workload caused by frequently building global ordinals due to frequent refreshes, increase the refresh interval.

# Pre-sort indexes at insertion time

[Index sorting](https://www.elastic.co/blog/index-sorting-elasticsearch-6-0) can be used to pre-sort indices at insertion time as opposed to at query time, which should improve the performance of range queries and sort operations. Note that this will increase the cost of indexing documents into Elasticsearch.

# Take advantage of the node query cache (cache filter results)

The [Node query cache](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-cache.html) can be used for efficiently caching results of [filter operations](https://www.elastic.co/guide/en/elasticsearch/reference/6.4/query-filter-context.html). This is effective if the same filter is executed multiple times, but changing even a single value within the filter means that a new filter result will need to be computed.

For example, queries that use “[now](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-range-query.html)” within the filter context cannot be cached since the value of now is constantly changing. Such requests can be made more cacheable by applying [datemath](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-range-query.html#ranges-on-dates) on the now field to round it to the nearest minute/hour/etc, so that the filter results can be cached and re-used for queries that appear within the same interval that has been rounded to.

# General Elasticsearch settings

Read the following official Elasticsearch documentation for more details on tuning an Elasticsearch cluster:

- [Important system configuration](https://www.elastic.co/guide/en/elasticsearch/reference/7.0/system-config.html)
- [Tune for search speed](https://www.elastic.co/guide/en/elasticsearch/reference/7.0/tune-for-search-speed.html)
- [Tune for indexing speed](https://www.elastic.co/guide/en/elasticsearch/reference/7.0/tune-for-indexing-speed.html)
- [Tune for disk usage](https://www.elastic.co/guide/en/elasticsearch/reference/7.0/tune-for-disk-usage.html)

Additional information on tuning slow queries can be found in [this blog about advanced Elasticsearch tuning](https://www.elastic.co/blog/advanced-tuning-finding-and-fixing-slow-elasticsearch-queries).

In addition to the above, having too many shards is a common cause of performance problems. [This blog about sharding](https://www.elastic.co/blog/how-many-shards-should-i-have-in-my-elasticsearch-cluster) gives good rules of thumb to follow.

The JVM heap size should generally be set to a maximum of 30GB. [This blog](https://www.elastic.co/blog/a-heap-of-trouble) gives a good description of why setting this value higher than 30GB is generally undesirable.

[Swapping is bad for performance](https://www.elastic.co/guide/en/elasticsearch/reference/current/setup-configuration-memory.html) and should be disabled.

# Conclusion

In this blog post, we have covered a few strategies for improving the aggregation performance of your Elasticsearch cluster.
