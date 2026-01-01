---
title: "Counting unique beats agents sending data into Elasticsearch"
date: 2019-07-18
slug: counting-unique-beats-agents-elasticsearch
aliases:
  - /2019/07/18/counting-unique-beats-agents-elasticsearch/
---

## Introduction

When using Beats with Elasticsearch, it may be useful to keep track of how many unique agents are sending data into an Elasticsearch cluster, and how many documents each agent is submitting. Such information for example could be useful for detecting if beats agents are behaving as expected.

In this blog post, I first discuss how to efficiently specify a filter for documents corresponding to a particular time range, followed by several methods for detecting how many beats agents are sending documents to Elasticsearch within the specified time range.

Note that the techniques discussed in this blog have limitations (discussed below) when the number of agents becomes very large. As an alternative to the techniques discussed in this blog post, the data coming from beats could transformed into an additional (new) index to make counting the number of beats agents more efficient and accurate, at the expense of additional up-front work being done at ingest time. This approach will be discussed in a future blog post (link will be placed here once written).

## How to filter for documents in a specific time range

This section describes how to efficiently filter for documents from a particular time range. In the following example, we filter for documents that were received yesterday:

```
GET filebeat-*/_search
{
  "query": {
    "bool": {
      "filter": {
        "range": {
          "@timestamp": {
            "gte": "now-1d/d",
            "lt" : "now/d"
          }
        }
      }
    }
  },
  "sort": [{"@timestamp": "desc"}]
}
```

Notice that we use the [filter context](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-filter-context.html#query-filter-context) for the range query. Using the filter context is efficient for two reasons:

1. Operations inside a filter context must answer a yes/no question - either documents fall into the time range or they do not. Because this is a yes/no question, a [\_score](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-request-sort.html) is not computed when filtering documents like this.
2. The data inside a filter can be efficiently cached by the [Node Query Cache](https://www.elastic.co/guide/en/elasticsearch/reference/7.2/query-cache.html), which "caches queries which are being used in a filter context".

It is worth highlighting that if the parameters inside the filter are different on each query, then the results of the filter cannot be efficiently cached. This would be the case if the range that is being queried is continually changing. This may unintentionally occur if "now" is used inside a range query without any rounding.

In the above example we ensure that the filter can cache documents by using [date math](https://www.elastic.co/guide/en/elasticsearch/reference/current/common-options.html#date-math) to round the range that we are searching in to the nearest day (as indicated by the "/d"). Compare this to the following which would give us all documents in the 24 hours prior to the current moment.

```
GET filebeat-*/_search
{
  "query": {
    "bool": {
      "filter": {
        "range": {
          "@timestamp": {
            "gte": "now-1d",
            "lt" : "now"
          }
        }
      }
    }
  },
  "sort": [{"@timestamp": "desc"}]
}
```

Note that the above filter cannot be cached because "now" is changing at every millisecond.

A middle-ground may be to round to the nearest hour to allow the filter to be cached most of the time, except once per hour when the range is modified. Rounding to the nearest hour could be done as follows:

```
GET filebeat-*/_search
{
  "query": {
    "bool": {
      "filter": {
        "range": {
          "@timestamp": {
            "gte": "now-1d/h",
            "lt" : "now/h"
          }
        }
      }
    }
  },
  "sort": [{"@timestamp": "desc"}]
}
```

Now that we have covered how to efficiently query for a documents in a particular time range, we are ready to demonstrate how to count the number of unique beats agents that are submitting documents to Elasticsearch.

## A basic query to get a count of unique agents

To get an approximate count of unique beats agents we can use a [cardinality aggregation](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-cardinality-aggregation.html) as shown below.

```
POST filebeat-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": {
        "range": {
          "@timestamp": {
            "gte": "now-1d/d",
            "lt" : "now/d"          
          }
        }
      }
    }
  },
  "aggs" : {
      "unique_agent_id_count" : {
          "cardinality" : {
              "field" : "agent.id.keyword",
              "precision_threshold": 500 
          }
      }
  }
}
```

Note that we first filter documents by time (in this case documents from yesterday), and then execute the  cardinality aggregation on the filtered set of documents . Also notice that the size is set to 0 – this tells ES that we are not interested in seeing the actual documents that match the range query, we just want to see the results of the cardinality aggregation done _across_ those documents.

## Get an example document from each agent using field collapsing

The example below demonstrates how to use [field collapsing](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-request-collapse.html) to return the \_source of a single document corresponding to each beats agent that submitted a document yesterday. Be aware that by default a search will only return 10 hits. In order to see all documents that match a given query the size should be increased, or if a large number of results are expected then pagination techniques should be used. In the example below we have set the size to 100, which will return up to 100 unique agents.

```
GET filebeat-*/_search
{
  "size" : 100,
  "query": {
    "bool": {
      "filter": {
        "range": {
          "@timestamp": {
            "gte": "now-1d/d",
            "lt": "now/d"
          }
        }
      }
    }
  },
  "collapse": {
    "field": "agent.id.keyword"
  },
  "sort": [
    {
      "@timestamp": "desc"
    }
  ]
}
```

## Get an example document from each agent using a terms aggregation and top hits

We can use a [terms aggregation](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-terms-aggregation.html) and [top hits aggregation](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-top-hits-aggregation.html) to get each unique agent as well as a count of the number of documents submitted from each unique agent. Be aware that this code is likely less efficient than the above and may not be practical if a very large number of agents are reporting into Elasticsearch.

```
GET filebeat-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": {
        "range": {
          "@timestamp": {
            "gte": "now-1d/d",
            "lt" : "now/d"
          }
        }
      }
    }
  },
  "aggs": {
    "unique_agents": {
      "terms": {
        "field": "agent.id.keyword",
        "size": 500,
      },
      "aggs": {
        "get_a_single_doc_for_each_unique_id": {
          "top_hits": {
            "sort": [
              {
                "@timestamp": {
                  "order": "desc"
                }
              }
            ],
            "size": 1
          }
        }
      }
    }
  }
}
```

There are three "size" settings in the code above:

1. We have set the size to 0 for the query results - this just means that we don't return the documents that match the range query, as we are only interested in the results of the aggregation.
2. A terms aggregation by default will only return the top 10 hits. In the example above we have increased the size of the terms aggregation to 500. Be careful, as setting this to a very large value to handle a very large number of agents may be slow. For a very large number of agents, terms aggregations may become infeasible.
3. Inside the top hits aggregations, we have specified a size of 1, meaning that a single document will be returned for each term.

## Conclusion

In this blog, we have demonstrated how to ensure the best performance when filtering for documents, followed by several methods for detecting how many unique beats agents are submitting documents into an Elasticsearch cluster.
