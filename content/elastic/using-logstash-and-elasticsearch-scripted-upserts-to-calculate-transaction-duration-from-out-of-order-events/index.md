---
title: "Using Logstash and Elasticsearch to calculate transaction duration in a microservices architecture"
date: 2020-09-16
slug: using-logstash-and-elasticsearch-scripted-upserts-to-calculate-transaction-duration-from-out-of-order-events
aliases:
  - /2020/09/16/using-logstash-and-elasticsearch-scripted-upserts-to-calculate-transaction-duration-from-out-of-order-events/
---

# Introduction

Elasticsearch  allows you to unify your observability data in a powerful datastore so you can search and apply interactive analytics in real time to a huge number of use cases.

In one such use case, you may be using Elasticsearch to monitor a system that is composed of multiple microservices that process a given transaction. For such a system, you may be collecting an event corresponding to when the first microservice in the system starts processing the transaction, and another event corresponding to when the last microservice in the system finishes processing the transaction. In such an approach, each event should include a field with the transaction identifier, which will allow multiple events corresponding to a single transaction to be combined for analysis.

In this blog I discuss how Elasticsearch in combination with Logstash may be used to ingest multiple events that correspond to a given transaction as it is processed by multiple microservices, and how to calculate the time difference between these different events, which I will refer to as the "transaction duration".

The approach discussed here will work even if the events corresponding to a given transaction arrive to Logstash out-of-order, and it could be easily extended to compute delays between any microservices that process a given transaction.

# A note about event ordering

If the events corresponding to a given transaction are guaranteed to arrive in order, then it may be possible to use [Logstash's Elapsed filter plugin](https://www.elastic.co/guide/en/logstash/current/plugins-filters-elapsed.html).

Alternatively, the approach _described in this article_ should work regardless of the order which events arrive in.

# Using scripted upserts to transform data

In a previous blog post, I described [how to use Logstash and Elasticsearch scripted upserts to transform data](https://alexmarquardt.com/2019/12/17/logstash-and-elasticsearch-painless-scripted-upserts-transform-data/). The approach in this blog is very similar, but has the explicit goal of calculating the duration between the "start" and "end" events for a given transaction.

The approach described in this blog will ultimately result in two indices being written into Elasticsearch. One index will contain _original_ documents corresponding to each monitoring event, and another index will contain _transformed_ documents which will track the transaction duration.

For the purposes of this blog, we expect events to contain a "@timestamp" field, a "tags" array that contains a value of "start\_event" or "end\_event" somewhere in the array, and a transaction identifier which we have stored in a field called "ident". For example, a document could look as follows:

```
{
  "message": "abc",
  "ident": "id1",
  "@timestamp": "2020-08-18T19:43:36.000Z",
  "other_field": "other_val 1",
  "tags": [
    "start_event"
  ]
}
```

As we will ultimately be using Logstash to call Elasticsearch scripted upserts to compute the duration of each transaction, it is worth highlighting that Logstash sends the source of each document into the [scripted upsert](https://www.elastic.co/guide/en/logstash/7.5/plugins-outputs-elasticsearch.html#plugins-outputs-elasticsearch-scripted_upsert) as _params_._event_ rather than in the standard _ctx.\_source_ that we normally expect.

The following script will calculate the time difference between the "start\_time" and the "end\_time" even if the end event arrives before the start event.

```
POST _scripts/calculate_transaction_duration
{
  "script": {
  "lang": "painless",
  "source": """
  

        def position_of_start_event_in_tags = params.event['tags'].indexOf('start_event');

        // if this is a "start event" then store the timestamp in the start_time field
        if (position_of_start_event_in_tags >= 0) {
          ctx._source['start_time'] = params.event['@timestamp']
        }
      
        def position_of_end_event_in_tags = params.event['tags'].indexOf('end_event');

        // if this is a "end event" then store the timestamp in the end_time field
        if (position_of_end_event_in_tags >= 0) {
          ctx._source['end_time'] = params.event['@timestamp']
        }
        
        // if both start and end times exist, calculate the difference 
        if (ctx._source.containsKey('start_time') && ctx._source.containsKey('end_time')) {
          ctx._source['duration_in_seconds'] = ChronoUnit.MILLIS.between(ZonedDateTime.parse(ctx._source['start_time']), ZonedDateTime.parse(ctx._source['end_time']))/1000;
        }
        // OPTIONAL COPY (PROBABLY NOT NEEDED)  - copy remaining fields into the _source
        //for (x in params.event.entrySet()) {
        //  ctx._source[x.getKey()] = x.getValue();
        //}

    """
  }
}

```

We can then test the above script directly from Dev tools by running both of the following commands (in any order) which will update the document with an _\_id_ of "id1" in the _test\_script_ index:

```
POST test_script/_doc/id1/_update
{
  "scripted_upsert": true,
  "script": {
    "id": "calculate_transaction_duration",
    "params": {
      "event": {
        "message": "abc", "ident": "id1", "@timestamp": "2020-08-18T19:43:36.000Z", "other_field": "other_val 1", "tags": ["start_event"]
      }
    }
  },
  "upsert": {}
}

POST test_script/_doc/id1/_update
{
  "scripted_upsert": true,
  "script": {
    "id": "calculate_transaction_duration",
    "params": {
      "event": {
        "message": "def", "ident": "id1", "@timestamp": "2020-08-18T19:53:36.000Z", "other_field": "other_val 2", "tags": ["end_event"]
      }
    }
  },
  "upsert": {}
}
```

After running the above code, we can view the document that contains the transaction duration as follows:

```
GET test_script/_doc/id1
```

Which will respond with the following:

```
 {
  "_index" : "test_script",
  "_type" : "_doc",
  "_id" : "id1",
  "_version" : 2,
  "_seq_no" : 4,
  "_primary_term" : 3,
  "found" : true,
  "_source" : {
    "start_time" : "2020-08-18T19:43:36.000Z",
    "end_time" : "2020-08-18T19:53:36.000Z",
    "duration_in_seconds" : 600
  }
}
```

We now have scripted upserts working and tested within Elasticsearch. Now let's get this working from Logstash.

The following Logstash pipeline will send two transactions each with two events into Elasticsearch. Notice that the last two events corresponding to the transaction "id2" are out-of-order. This is no issue, as the script that we demonstrated above will handle this correctly.

```
input {
  # The generator creates input events.
  # Notice how the events associated with id2 are "out of order"
  generator {
    lines => [
     '{"message": "abc", "ident": "id1", "@timestamp": "2020-08-18T19:43:36.000Z", "other_field": "other_val 1", "tags": ["start_event"]}',
     '{"message": "def", "ident": "id1", "@timestamp": "2020-08-18T19:53:36.000Z", "other_field": "other_val 2", "tags": ["end_event"]}',
     '{"message": "ghi", "ident": "id2", "@timestamp": "2020-08-20T19:43:56.000Z", "other_field": "other_val 4", "tags": ["end_event"]}',
     '{"message": "jkl", "ident": "id2", "@timestamp": "2020-08-20T19:43:36.000Z", "other_field": "other_val 3", "tags": ["start_event"]}'
    ]
    count => 1
    codec =>  "json"
  }
}
filter {}
output {

  # Transformed data
  elasticsearch {
    index => "transaction_duration"
    document_id => "%{ident}"
    action => "update"
    scripted_upsert => true
    script_lang => ""
    script_type => "indexed"
    script => "calculate_transaction_duration"
  }

  # Original data
  elasticsearch {
    index => "transaction_original"
  }
}
```

The above pipeline can be saved into a file called _scripted-elapsed.conf_ and directly executed as follows:

```
/bin/logstash -f scripted-elapsed.conf --config.reload.automatic
```

After running the above Logstash pipeline, there will be two indices created in the locally running Elasticsearch. One is the index that contains the original events and is called "transaction\_original", and the other is the _transformed_ index called "transaction\_duration" that contains the duration of each transaction.

We can look at the "transaction\_duration" index with the following command:

```
GET transaction_duration/_search
```

Which will respond with the following two documents which correspond to each transaction:

```
    "hits" : [
      {
        "_index" : "transaction_duration",
        "_type" : "_doc",
        "_id" : "id2",
        "_score" : 1.0,
        "_source" : {
          "end_time" : "2020-08-20T19:43:56.000Z",
          "start_time" : "2020-08-20T19:43:36.000Z",
          "duration_in_seconds" : 20
        }
      },
      {
        "_index" : "transaction_duration",
        "_type" : "_doc",
        "_id" : "id1",
        "_score" : 1.0,
        "_source" : {
          "end_time" : "2020-08-18T19:53:36.000Z",
          "start_time" : "2020-08-18T19:43:36.000Z",
          "duration_in_seconds" : 600
        }
      }
    ]
```

We have now verified that the script to calculate event duration is functioning correctly when we call it from Logstash!

# Conclusion

In this blog post, I first discussed how a given transaction may result in multiple events being sent into Elasticsearch. I then showed how you can use Logstash to execute scripted upserts which calculate the duration of a given transaction by comparing the timestamps of the related events.
