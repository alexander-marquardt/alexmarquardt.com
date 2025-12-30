---
title: "Re-directing Elasticsearch documents with out-of-range timestamps that (would) fail to get written into Time Series Data Streams"
date: 2024-04-16
tags: 
  - "elasticsearch"
---

## Introduction

Elasticsearch [Time Series Data Streams (TSDS)](https://www.elastic.co/guide/en/elasticsearch/reference/current/tsds.html) are designed to provide an efficient and scalable way to handle time-based data within the Elasticsearch ecosystem. This feature is specifically optimized for storing, searching, and managing time-series data such as metrics, and events, where data is continuously indexed in chronological order. However, if events arrive with timestamps that fall outside of a pre-defined range, they will be lost.  
  
In this blog I will demonstrate logic that can be added to an Elasticsearch ingest pipeline which can be used to intercept documents that would be rejected by the TSDS index due to timestamp range issues, and to instead redirect them to a "failed" index. The documents that are redirected to the "failed" index may (for example) be used to raise alerts and examined.

## Motivation

As discussed in a previous blog on [Storing ingest time and calculating ingest lag in Elasticsearch](https://alexmarquardt.com/2020/06/02/storing-ingest-time-and-calculating-ingest-lag-in-elasticsearch/), there are several reasons why events may have incorrect timestamps. If such events are to be sent into a TSDS, they may be rejected due to falling outside of the range that is allowed by the [look\_back\_time or the look\_ahead time](https://www.elastic.co/guide/en/elasticsearch/reference/current/tsds-index-settings.html). Additionally, if ILM is used then older indices may already be set to read-only, which may cause events with old timestamps to silently fail to be written.  
  
It is often useful to know if documents that should have been indexed into a TSDS are rejected, so that they can be further investigated. This blog presents a simple ingest pipeline script that can be used to redirect such documents to a "failed" index for further investigation.

## Design

In order to ensure that no documents with incorrect timestamps disappear, you may wish to set the [look\_ahead\_time and look\_back\_time intervals](https://www.elastic.co/guide/en/elasticsearch/reference/current/tsds-index-settings.html) to a slightly larger time range than what we use in the script presented below. This will ensure that the script catches all timestamp range issues, rather than the indexer failing and the event disappearing. Additionally, if you know that due to ILM running, older indices become read-only, you would want to ensure that the time range defined in the script below would send these documents to a separate index rather than silently failing to write to the read-only index.  
  
Below is a script that gives a general demonstration of the concept of how to redirect events to a different index based on their timestamp. The script should be adjusted so that the time ranges are relevant to your particular situation.

First, lets setup an index template for a data stream as follows:

```

PUT /_index_template/my-data-stream-template?pretty
{
  "index_patterns": [
    "my-data-stream*"
  ],
  "data_stream": {},
  "template": {
    "settings": {
      "index": {
        "mode": "time_series",
        "routing_path": [
          "host"
        ],
        "number_of_replicas": 0,
        "number_of_shards": 2
      }
    },
    "mappings": {
      "properties": {
        "@timestamp": {
          "type": "date"
        },
        "bytes": {
          "type": "long",
          "time_series_metric": "gauge"
        },
        "host": {
          "type": "keyword",
          "time_series_dimension": true
        }
      }
    }
  }
}
```

You can then define an ingest pipeline that validates time ranges on the incoming events as follows:

```
PUT _ingest/pipeline/my-timestamp-pipeline
{
  "description": """If a document falls outside of the time ranges that would result in it being correctly written into a time series data stream, then send it to a special index for further evaluation""",
  "processors": [
    {
      "set": {
        "field": "ingest_time",
        "value": "{{_ingest.timestamp}}"
      }
    },
    {
      "script": {
        "lang": "painless",
        "source": """
          def future_hours = 2;
          def past_hours = 2;
          
          // Parse the ingest time and original timestamp once
          ZonedDateTime ingestTime = ZonedDateTime.parse(ctx["ingest_time"]);
          ZonedDateTime eventTimestamp = ZonedDateTime.parse(ctx["@timestamp"]);
          
          // Check if the original timestamp is more than 2 hours earlier of the ingest time 
          // or more than 2 hours later than the ingest time
          if (eventTimestamp.isBefore(ingestTime.minusHours(past_hours)) || eventTimestamp.isAfter(ingestTime.plusHours(future_hours))) {
            ctx['_index'] = "timeseries_failures_index";
          } 
        """
      }
    }
    ]
}
```

And finally you can test the above script by passing in documents such as the following (be sure to update the timestamp to fall within a few hours of the current time that you are testing the script):

```
PUT /my-data-stream/_bulk?refresh&pipeline=my-timestamp-pipeline&pretty
{"create": {}}
{"@timestamp":"2024-04-16T18:11:30Z","host":"host_c", "bytes":1234}
{"create": {}}
{"@timestamp":"2024-04-16T19:11:30Z","host":"host_c", "bytes":2345}
```

## Conclusion

In this article, I have showed how a simple ingest pipeline can be written which will detect documents that have timestamps which would cause them to fail to index in an Elasticsearch Time Series Data Stream (TSDS). This is a proof of concept that can be extended and adapted to your ingest requirements.
