---
title: "Using slow logs in Elastic Cloud Enterprise"
date: 2020-04-26
slug: using-slow-logs-in-elastic-cloud-enterprise
aliases:
  - /using-slow-logs-in-elastic-cloud-enterprise/
---

April 26, 2020

# Authors

- Tom Schreiber
- Alex Marquardt

# Version

This blog article is based on ECE 2.4.3.

# Introduction

[Elastic Cloud Enterprise](https://www.elastic.co/guide/en/cloud-enterprise/2.4/Elastic-Cloud-Enterprise-overview.html) (ECE) is a platform designed to ease the management, deployment, and configuration of multiple Elasticsearch clusters through a single administrative user interface. ECE, is the same product that powers the [Elasticsearch Service](https://www.elastic.co/elasticsearch/service) hosted offering, and is available for installation on customer-managed servers. ECE can be deployed anywhere - on public or private clouds, virtual machines, or even on bare metal hardware. Once installed, ECE allows Elasticsearch clusters to be created, upgraded, or deleted with the click of a button.

When using Elasticsearch, a very important metric from a client perspective is how long it takes for queries to be satisfied. If query response time is not measured and monitored, then it is difficult to know how well Elasticsearch is performing.

Elasticsearch can be configured to write [slow operations to log files](https://www.elastic.co/guide/en/elasticsearch/reference/7.6/index-modules-slowlog.html). Because ECE builds clusters on top of Docker containers, direct access to Elasticsearch log files is non trivial. In order to provide easy access to these logs, ECE ingests logs from managed clusters into an [internal centralized Logging and Metrics cluster](https://www.elastic.co/guide/en/cloud-enterprise/current/ece-monitoring-ece.html). However, the Logging and Metrics cluster is not generally accessible by non-administrator users, and the slow logs in this cluster are not structured in a way that can be used for driving dashboards or creating alerts.

In this blog, we will show how to extract slow logs from the Logging and Metrics cluster and add structure to them as they are driven into a separate analysis cluster. This separate analysis cluster can then be used for detecting performance issues and driving Kibana dashboards.

# Why not use the built-in Logging and Metrics cluster for analysis, alerting, and dashboards?

ECE internally uses [Filebeat](https://www.elastic.co/guide/en/beats/filebeat/current/filebeat-overview.html) to ingest the slow log entries from all of the nodes that are under ECE management into its internal Logging and Metrics cluster. However, directly using the slow logs data in the Logging and Metrics cluster is generally undesirable for the following reasons:

1. The slow logs information that is stored in the Logging and Metrics cluster is stored as a single string, which is not useful for creating dashboards or for viewing metrics.
2. At the time of writing, the Logging and Metrics cluster is built on Elasticsearch 6.8.5 which does not contain as much functionality as newer versions of Elasticsearch.
3. Given that the Logging and Metrics cluster is designed for internal usage, we do not wish to burden this internal cluster with Kibana dashboards and user requests.
4. We may wish to give wide access to information about slow operations. Such wide access directly to the internal Logging and Metrics cluster would be undesirable, as the monitoring functions could be compromised if it were to be overloaded.

For these reasons, we will show how to extract slow logs from the Logging and Metrics cluster into a new cluster within our ECE deployment.

# Create additional clusters

We will [create two additional clusters](https://www.elastic.co/guide/en/cloud-enterprise/2.4/ece-create-deployment.html). An analysis cluster which will be used for monitoring and alerting as well as driving Kibana dashboards, and a slow queries cluster where we will simulate a workload that generates slow logs entries.

By default, slow logs from all ECE clusters are combined together into _cluster-logs-\*_ indices in the Logging and Metrics cluster.

# Enable the sample data and execute queries

For demonstration purposes, we will install the demo _kibana\_sample\_data\_flights_ into our slow queries cluster as described in [Explore Kibana using sample data](https://www.elastic.co/guide/en/kibana/7.6/tutorial-sample-data.html).

# Enabling slow logs for the sample data

We enable logging of all queries against the _kibana\_sample\_data\_flights_ index, which can be accomplished by logging all queries that take 0ms or longer. In the Kibana of the slow queries cluster, we can execute the following command in [Kibana Dev Tools](https://www.elastic.co/guide/en/kibana/7.6/console-kibana.html):

```
PUT /kibana_sample_data_flights/_settings
{
    "index.search.slowlog.threshold.query.info": "0s",
    "index.search.slowlog.threshold.fetch.info": "0s",
    "index.search.slowlog.level": "info"
}
```

Because the above command will write an entry to the slowlog file for every query that is executed against the _kibana\_sample\_data\_flights_ index, setting thresholds to zero should not be done for production deployments. Doing so would likely generate a large workload as well as excessive amounts of logging data.

# Execute queries against the sample data

We can now generate slow logs entries by performing simple queries from Kibana against the _kibana\_sample\_data\_flights_ index in the slow queries cluster. For example, a query for flights where the destination country is Australia could be done as follows:

```
GET kibana_sample_data_flights/_search
{
  "query": {
    "match": {
      "DestCountry": "AU"
    }
  }
}
```

## View the slow logs in the Logging and Metrics cluster

We can confirm that the above query generated an event by logging into the Kibana instance associated with the Logging and Metrics cluster. Once in Kibana for the Logging and Metrics cluster, go to Discover and select the _cluster-logs-\*_ index pattern, and enter in the following query in the search input:

```
source: *slowlog*
```

Assuming that there are no other operations generating slow events, this query should return documents that contain information about the query that we just executed on the slow queries cluster. As the slow logs may be created on each shard which the query hits, there may be multiple slow log entries created by a single query.

We are interested in the _message_ field in the returned document, which contains the information about the query that we just executed, and which should look similar to the following:

```
"message": "[2020-05-14T20:39:29,644][INFO ][index.search.slowlog.fetch.S-OhddFHTc2h6w8NDzPzIw] [instance-0000000000] [kibana_sample_data_flights][0] took[3.7ms], took_millis[3], total_hits[416 hits], types[], stats[], search_type[QUERY_THEN_FETCH], total_shards[1], source[{\"query\":{\"match\":{\"DestCountry\":{\"query\":\"AU\",\"operator\":\"OR\",\"prefix_length\":0,\"max_expansions\":50,\"fuzzy_transpositions\":true,\"lenient\":false,\"zero_terms_query\":\"NONE\",\"auto_generate_synonyms_phrase_query\":true,\"boost\":1.0}}}}], id[], "
```

Notice how the information about the slow query is stored in a single string. In order to properly analyse this information, the data needs to be extracted and structured. The remainder of this blog shows how this can be done.

## Extract fields from the message string

We must parse the message field that contains the slow log information, and extract useful data in order to be able to do meaningful analysis. The following ingest pipeline will extract the fields from the slowlog message string using a [grok processor](https://www.elastic.co/guide/en/elasticsearch/reference/7.6/grok-processor.html).

```
PUT _ingest/pipeline/sl-pipeline
{
  "processors": [
    {
      "grok": {
        "field": "message",
        "patterns": [
"""\[%{TIMESTAMP_ISO8601:event.end}\]\[%{LOGLEVEL:log.level}\s*\]\[%{DATA:slowlog.type}\]\s*\[%{DATA:host.name}\]\s*\[%{DATA:slowlog.index}\]\s*\[%{DATA:slowlog.shard:int}]\stook\[%{DATA:slowlog.took}\],\stook_millis\[%{DATA:slowlog.took_millis:float}\],\stotal_hits\[%{DATA:slowlog.total_hits:int}\shits\]\,\stypes\[%{DATA:slowlog.types}\],\sstats\[%{DATA:slowlog.stats}\],\ssearch_type\[%{DATA:slowlog.search_type}\],\stotal_shards\[%{DATA:slowlog.total_shards:int}\],\ssource\[%{GREEDYDATA:slowlog.source}\],\sid\[%{DATA:slowlog.x-opaque-id}\]"""
        ]
      }
    },
    {
      "script": {
        "lang": "painless",
        "source": " ctx.event.duration = (ctx.slowlog.took_millis) * params.ms_to_ns_multiplier",
        "params": {
          "ms_to_ns_multiplier": 1000000
        }
      }
    },
    {
      "date_index_name": {
        "field": "@timestamp",
        "index_name_prefix": "slowlog-",
        "date_rounding": "M"
      }
    }
  ]
}
```

As we wish to use the [Elastic Common Schema (ECS)](https://www.elastic.co/guide/en/ecs/current/index.html) for as many fields as possible, we store the duration of the query in _event.duration_, which is [defined as the event duration in nanoseconds](https://www.elastic.co/guide/en/ecs/current/ecs-event.html). Therefore, we calculate _event.duration_ by multiplying the _took\_millis_ value by 1000000. This does not actually result in nanosecond resolution. If more resolution is required, then _event.duration_ should be calculated based on _took_ rather than _took\_millis_. However, because _took_ contains a string with both a number and units, this would require additional processing which is out of scope of this blog.

## Grok

The above grok expression was tested with ECE 2.4.3, and has ingested logs from an Elasticsearch cluster running version 7.5.0. However, because small changes to the format can break the above expression, it is worth noting that Kibana has a [grok debugger](https://www.elastic.co/guide/en/kibana/7.6/xpack-grokdebugger.html) that can be helpful when trying to debug a grok expression that does not work as expected.

## Test the pipeline

The above pipeline can be tested with the [simulate pipeline API](https://www.elastic.co/guide/en/elasticsearch/reference/7.5/simulate-pipeline-api.html) as follows:

```
POST /_ingest/pipeline/sl-pipeline/_simulate
{
  "docs": [
    {
      "_index": "test_idx",
      "_id": "1",
      "_source": {
        "@timestamp": "2020-05-14T20:39:29.691Z",
        "message": """[2020-05-14T20:39:29,644][INFO ][index.search.slowlog.fetch.S-OhddFHTc2h6w8NDzPzIw] [instance-0000000000] [kibana_sample_data_flights][0] took[3.7ms], took_millis[3], total_hits[416 hits], types[], stats[], search_type[QUERY_THEN_FETCH], total_shards[1], source[{"query":{"match":{"DestCountry":{"query":"AU","operator":"OR","prefix_length":0,"max_expansions":50,"fuzzy_transpositions":true,"lenient":false,"zero_terms_query":"NONE","auto_generate_synonyms_phrase_query":true,"boost":1.0}}}}], id[], """
      }
    }
  ]
}
```

Which should respond with the following that shows us how documents will look after being processed by the pipeline:

```
{
  "docs" : [
    {
      "doc" : {
        "_index" : "<slowlog-{2020-05-14||/M{yyyy-MM-dd|UTC}}>",
        "_type" : "_doc",
        "_id" : "1",
        "_source" : {
          "@timestamp" : "2020-05-14T20:39:29.691Z",
          "log" : {
            "level" : "INFO"
          },
          "slowlog" : {
            "took" : "3.7ms",
            "total_shards" : 1,
            "types" : "",
            "took_millis" : 3.0,
            "total_hits" : 416,
            "stats" : "",
            "x-opaque-id" : "",
            "index" : "kibana_sample_data_flights",
            "source" : """{"query":{"match":{"DestCountry":{"query":"AU","operator":"OR","prefix_length":0,"max_expansions":50,"fuzzy_transpositions":true,"lenient":false,"zero_terms_query":"NONE","auto_generate_synonyms_phrase_query":true,"boost":1.0}}}}""",
            "shard" : 0,
            "type" : "index.search.slowlog.fetch.S-OhddFHTc2h6w8NDzPzIw",
            "search_type" : "QUERY_THEN_FETCH"
          },
          "host" : {
            "name" : "instance-0000000000"
          },
          "message" : """[2020-05-14T20:39:29,644][INFO ][index.search.slowlog.fetch.S-OhddFHTc2h6w8NDzPzIw] [instance-0000000000] [kibana_sample_data_flights][0] took[3.7ms], took_millis[3], total_hits[416 hits], types[], stats[], search_type[QUERY_THEN_FETCH], total_shards[1], source[{"query":{"match":{"DestCountry":{"query":"AU","operator":"OR","prefix_length":0,"max_expansions":50,"fuzzy_transpositions":true,"lenient":false,"zero_terms_query":"NONE","auto_generate_synonyms_phrase_query":true,"boost":1.0}}}}], id[], """,
          "event" : {
            "duration" : 3000000.0,
            "end" : "2020-05-14T20:39:29,644"
          }
        },
        "_ingest" : {
          "timestamp" : "2020-05-15T09:33:12.535Z"
        }
      }
    }
  ]
}
```

Note that the _slowlog.source_ field contains the query that was executed. Additionally, the duration of the query is now available in the _event.duration_ field and can be used for analysis and in dashboards.

## Reindex data from the Logging and Metrics cluster into the analysis cluster

Before executing a “reindex from remote” command, it is necessary to [whitelist the remote cluster](https://www.elastic.co/guide/en/elasticsearch/reference/7.6/reindex-upgrade-remote.html) that data will be pulled from. Also, to keep this blog simple we turn off SSL certificate verification which removes protection against man in the middle attacks and certificate forgery. This is only done for demonstration purposes as security configuration is not the focus of this blog. Such a liberal security configuration should not generally be used for production systems. These settings will be modified in the _elasticsearch.yml_ file.

In ECE, _elasticsearch.yml_ can be modified by clicking on the deployment name, and then clicking on “Edit” on the left menu. This will show a screen with the various nodes in the deployment. Under the data node, there is a “User setting overrides” button, which will allow the _elasticsearch.yml_ file to be modified. We add the following lines which enable reindexing from any remote server as well as SSL to be used without certificate verification:

```
reindex.remote.whitelist: ["*.*"]
reindex.ssl.verification_mode: none
```

In order to ingest the slow logs into the analysis cluster, we execute [reindex from remote](https://www.elastic.co/guide/en/elasticsearch/reference/current/reindex-upgrade-remote.html) to pull data from the Logging and Metrics cluster, and pass all documents through the ingest processor called _sl-pipeline_ that we previously described. The reindex operation can be executed on the analysis cluster with curl as follows:

```
curl -XPOST "https://<analysis cluster URL>:9243/_reindex" -u elastic:<analysis cluster password> -k -H 'Content-Type: application/json' -d' 
{ 
 "source": { 
    "remote": { 
      "host": "https://<Logging and Metrics cluster URL>:9243", 
      "username": "elastic", 
      "password": "<Logging and Metrics cluster password> " 
    }, 
    "index": "cluster-logs-*", 
    "query": { 
      "bool": { 
        "filter": [ 
          { 
            "range": { 
              "@timestamp": { 
                "gte": "now-1h", # ← this should be modified based on the frequency of executing this reindex operation
                "lt": "now" 
              } 
            } 
          },
          { 
            "query_string": { 
              "query": "source: *slowlog*", 
              "analyze_wildcard": true 
            } 
          } 
        ] 
      } 
    } 
  }, 
  "dest": { 
    "index": "fakename", # ← this name is unused as it is overwritten by the date_index_name processor in the ingest pipeline
    "pipeline": "sl-pipeline", 
    "op_type": "create" 
  }, 
  "conflicts": "proceed" 
}
'
```

Be sure to remove the comments starting with the “#” symbol from the above command before attempting to execute it, or it will not work correctly. 

## Result of the reindex operation

Once the above reindex operation has been executed, the analysis cluster should have documents that look like the following. These will be located in an index called _slowlog-<YYYY-MM-dd>_ which we declared in the pipeline called _sl-pipeline_. 

```
"_source" : {
  "@timestamp" : "2020-05-14T20:39:29.691Z",

  ...

  "log" : {
    "level" : "INFO"
  },
  "slowlog" : {
    "took" : "3.7ms",
    "total_shards" : 1,
    "types" : "",
    "took_millis" : 3.0,
    "total_hits" : 416,
    "stats" : "",
    "x-opaque-id" : "",
    "index" : "kibana_sample_data_flights",
    "source" : """{"query":{"match":{"DestCountry":{"query":"AU","operator":"OR","prefix_length":0,"max_expansions":50,"fuzzy_transpositions":true,"lenient":false,"zero_terms_query":"NONE","auto_generate_synonyms_phrase_query":true,"boost":1.0}}}}""",
    "shard" : 0,
    "type" : "index.search.slowlog.fetch.S-OhddFHTc2h6w8NDzPzIw",
    "search_type" : "QUERY_THEN_FETCH"
  },
  "host" : {
    "name" : "instance-0000000000"
  },
  "message" : """[2020-05-14T20:39:29,644][INFO ][index.search.slowlog.fetch.S-OhddFHTc2h6w8NDzPzIw] [instance-0000000000] [kibana_sample_data_flights][0] took[3.7ms], took_millis[3], total_hits[416 hits], types[], stats[], search_type[QUERY_THEN_FETCH], total_shards[1], source[{"query":{"match":{"DestCountry":{"query":"AU","operator":"OR","prefix_length":0,"max_expansions":50,"fuzzy_transpositions":true,"lenient":false,"zero_terms_query":"NONE","auto_generate_synonyms_phrase_query":true,"boost":1.0}}}}], id[], """,
  "event" : {
    "duration" : 3000000.0,
    "end" : "2020-05-14T20:39:29,644"
  }
},
```

As opposed to the documents that are stored in the Logging and Metrics cluster, these documents have a structure that includes fields that can be used for monitoring and alerting or driving dashboards. For example, the _event.duration_ field could be monitored for queries that take longer than a critical threshold, and dashboards could be created that show which queries are commonly slow. Monitoring and alerting solutions as well as example dashboards that are based on this data will be presented in a future blog post.

## Automate the execution of the reindex operation

The above reindex command can be stored in a shell script, and called from cron. For example, assuming that you have stored the above curl command in a file called _pull\_logs.sh_, the following would execute the above reindex operation once per minute:

```
crontab -e
* * * * * /path/to/pull_logs.sh
```

Note that because this would automate the reindex script to execute every minute, the data that is pulled from the Logging and Metrics cluster should include the last two minutes to reduce the possibility that documents are missed. This can be accomplished by specifying the range _now-2m_ on the _@timestamp_ field in the reindex operation that we previously presented. Because we execute the script every minute, and pull documents from the past 2 minutes, there will be some overlap which is intentional.

In order to avoid writing the same documents twice when executing the reindex command, we specify that only new documents should be inserted into the _slowlogs-\*_ index, by specifying _"op\_type": "create"_.

## Conclusion

In this blog, we showed how to extract slow logs from the Logging and Metrics cluster into a separate analysis cluster, which can be used for detecting performance issues and driving Kibana dashboards. In an upcoming blog, we will show how to create dashboards and alerts that use the data that has been ingested into the analysis cluster.
