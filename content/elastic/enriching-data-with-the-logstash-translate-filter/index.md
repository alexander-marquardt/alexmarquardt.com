---
title: "Enriching data with the Logstash translate filter"
date: 2020-03-06
slug: enriching-data-with-the-logstash-translate-filter
aliases:
  - /enriching-data-with-the-logstash-translate-filter/
---

March 6, 2020

## Introduction

[Logstash](https://www.elastic.co/logstash) is an open source, server-side data processing pipeline that ingests data from a multitude of sources, transforms it, and then sends it to one or more outputs. One use of Logstash is for enriching data before sending it to Elasticsearch.

Logstash supports several different [lookup plugin filters](https://www.elastic.co/guide/en/logstash/current/lookup-enrichment.html#geoip-def) that can be used for enriching data. Many of these rely on components that are external to the Logstash pipeline for storing enrichment data. On the other hand, the [translate filter plugin](https://www.elastic.co/guide/en/logstash/current/plugins-filters-translate.html) can be used for looking up data and enriching documents without dependencies. Therefore, in this blog article I focus on using Logstash with the translate filter plugin for enriching data.

## Enriching data with the translate filter plugin

An example Logstash pipeline that executes a translate filter lookup is given below. This filter searches in the translate dictionary for the key indicated by the value stored in the event’s “lookup\_id”, and stores the value retrieved from the translate dictionary in the “enrichment\_data” field. If the value from the “lookup\_id” is not found in the translate dictionary, then code will store the “fallback” value of “not\_found” in the “enrichment\_data” field.

```
input {
  # The generator creates an input event
  generator {
    lines => [
     '{"my_msg": "testing1234", "lookup_id": "1234"}'
    ]
    count => 1
    codec =>  "json"
  }
}

filter {
  # Enrich the event using the lookup_id
  translate {
    field => "[lookup_id]"
    destination => "[enrichment_data]"
    fallback => "not_found"
    dictionary => {
      "1234" => "1234 found in the dictionary"
      "5678" => "5678 also in the dictionary"
    }
  }
}

output {
  stdout { codec =>  "rubydebug" }
}
```

The above pipeline can be stored in a config file, and executed by running the following command:

```
./logstash -f <logstash config file>
```

Which should result in a document that contains a field called “enrichment\_data” that was populated by the translate filter plugin, as shown below:

```
{
           "@version" => "1",
    "enrichment_data" => "1234 found in the dictionary",
         "@timestamp" => 2020-03-04T12:21:16.989Z,
             "my_msg" => "testing1234",
          "lookup_id" => "1234",
           "sequence" => 0,
               "host" => "alexandersmbp2.lan"
}
```

In the event of an unsuccessful lookup, the output should look like the following:

```
{
    "enrichment_data" => "not_found",
           "@version" => "1",
         "@timestamp" => 2020-03-04T12:35:02.791Z,
               "host" => "alexandersmbp2.lan",
           "sequence" => 0,
             "my_msg" => "testing1234",
          "lookup_id" => "1234x"
}
```

## Using the translate plugin combined with JSON subdocuments

While the above approach is useful for simple key-value lookups, it may sometimes be necessary to enrich documents with more complex lookups. This can be achieved by embedding JSON subdocuments directly in the translate filter. Such a pipeline could look as follows:

```
input {
  # The generator creates an input event
  generator {
    lines => [
     '{"my_msg": "testing123", "lookup_id": "1234"}'
    ]
    count => 1
    codec =>  "json"
  }
}

filter {
  # Enrich the event using the lookup_id
  translate {
    field => "[lookup_id]"
    destination => "[enrichment_data]"
    fallback => '{"key1":"not_found"}'
    dictionary => {
      "1234" => {"key1" => "first 1" "key2" => 123 "key3" => "third 1"}
      "5678" => {"key1" => "first 2" "key2" => 456 "key3" => "third 2"}
    }
  }

  # Failed lookup - ensure JSON is stored
  if [enrichment_data] =='{"key1":"not_found"}' {
    json { 
      source => "enrichment_data" 
      target => "enrichment_data"
    }
  }
}

output {
  stdout { codec =>  "rubydebug" }
}

```

Note that in the above pipeline, because a “fallback” value can only contain a string, additional processing is done to ensure that failed lookups store an object in “enrichment\_data”.

In the event of a successful lookup, the output should look as follows:

```
{
          "lookup_id" => "1234",
           "@version" => "1",
    "enrichment_data" => {
        "key1" => "first 1",
        "key3" => "third 1",
        "key2" => 123
    },
         "@timestamp" => 2020-03-04T12:19:53.612Z,
           "sequence" => 0,
             "my_msg" => "testing123",
               "host" => "alexandersmbp2.lan"
}
```

And in the event of an unsuccessful lookup, the output should look like the following:

```
{
    "enrichment_data" => {
        "key1" => "not_found"
    },
             "my_msg" => "testing123",
         "@timestamp" => 2020-03-04T12:19:17.742Z,
           "@version" => "1",
               "host" => "alexandersmbp2.lan",
          "lookup_id" => "1234x",
           "sequence" => 0
}
```

## Using a JSON dictionary file with the translate filter plugin

The translate filter plugin supports large dictionaries, and has been tested with up to 100,000 key/values. For large dictionaries it may be convenient to store the [lookup values in an external file](https://www.elastic.co/guide/en/logstash/current/plugins-filters-translate.html#plugins-filters-translate-dictionary_path) rather than directly in the Logstash pipeline.

When using a JSON dictionary, it is possible to provide multi-valued dictionary values in an external JSON dictionary file that would look like the following:

```
{
  "1234":{"key1":"first 1", "key2":123, "key3":"third 1"},
  "5678":{"key1":"first 2", "key2":456, "key3":"third 2"}
}
```

And a Logstash pipeline that uses this JSON dictionary file is as follows:

```
input {
  # The generator creates an input event
  generator {
    lines => [
     '{"my_msg": "testing123", "lookup_id": "1234"}'
    ]
    count => 1
    codec =>  "json"
  }
}

filter {
  # Enrich the event using the lookup_id
  translate {
    field => "[lookup_id]"
    destination => "[enrichment_data]"
    fallback => '{"key1":"not_found"}'

    # ** Must set "/path/to/lookup.json" to your lookup file **
    dictionary_path => "/path/to/lookup.json"
  }

  # Failed lookup - ensure JSON is stored
  if [enrichment_data] == '{"key1":"not_found"}' {
    json { 
      source => "enrichment_data" 
      target => "enrichment_data"
    }
  }
}

output {
  stdout { codec =>  "rubydebug" }
}
```

Note that in the above pipeline, because a “fallback” value can only contain a string, additional processing is done to ensure that failed lookups store an object in “enrichment\_data”.   The output from this example pipeline should be the same as the previous example.

## Converting CSV to JSON

In some cases, data that is to be used for enriching documents is available in CSV files such as those that may be produced by Microsoft Excel. However, the translate filter plugin expects exactly two columns when used with CSV data. Therefore, in order to support multi-value lookups, multi-column CSV must be converted into a different format that supports more complex enrichments. One such format is JSON. Therefore, in this section we present a Python 3 script that can convert a CSV table into a JSON document that is suitable for the translate filter.

Given a CSV file that looks as follows:

```
lookup_id,key1,key2,key3
"1234","first 1",123,"third 1"
"5678","first 2",456,"third 2"
```

The script will generate an output file that is suitable for use by the translate plugin. The generated file will look as follows:

```
{
  "1234":{"key1":"first 1", "key2":123, "key3":"third 1"},
  "5678":{"key1":"first 2", "key2":456, "key3":"third 2"}
}
```

The source code for the Python script that creates the JSON from the CSV can be [found on github](https://github.com/alexander-marquardt/csv-to-json-for-logstash) and is also given below:

```
#!/usr/bin/env python

# This is written with python3 syntax

import csv
import os
import json

INPUT_FILE_NAME = 'lookup.csv'
INPUT_FILE_PATH = os.path.join(os.getcwd(), INPUT_FILE_NAME)
CSV_DELIMITER = ','

OUTPUT_FILE_NAME = 'lookup.json'
OUTPUT_FILE_PATH = os.path.join(os.getcwd(), OUTPUT_FILE_NAME)

LOOKUP_COL = "lookup_id"

# Each CSV line will be converted into a dictionary object, and pushed
# onto an array. This ensures that the generated json
# will have the same order as the lines in the CSV file.
array_of_ordered_dict = []

# function to convert the CSV into an array that contains a json-like
# dictionary for each line in the CSV file
def create_ordered_dict_from_input():
    with open(INPUT_FILE_PATH) as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=CSV_DELIMITER)
        print("Reading %s" % INPUT_FILE_PATH)
        for row in csv_reader:
            array_of_ordered_dict.append(row)

        print("Finished reading %s" % INPUT_FILE_PATH)
        return array_of_ordered_dict;

# Convert the array of dictionary objects into a json object.
def convert_array_of_ordered_dict_to_json(array_of_ordered_dict):

    print("Creating %s" % OUTPUT_FILE_PATH)
    f = open(OUTPUT_FILE_PATH, "w")

    # Create the json lookup table
    f.write("{\n")

    arr_len = len(array_of_ordered_dict)
    for idx, row in enumerate(array_of_ordered_dict):
        lookup_id = row[LOOKUP_COL]
        del row[LOOKUP_COL]

        # lookup_id is a dictionary key, with the json_dict as the value
        json_element = '"{0}" : {1}'.format(lookup_id, json.dumps(row))

        # If this is the last json element, then the dictionary should be closed rather than
        # adding a trailing comma.
        json_line = ''.join([json_element, "\n}\n"]) if (idx+1) == arr_len else ''.join([json_element, ",\n"])

        f.write(json_line)

    print("Finished writing %s" % OUTPUT_FILE_PATH)
    return 0

if __name__ == "__main__":
    array_of_ordered_dict = create_ordered_dict_from_input()
    convert_array_of_ordered_dict_to_json(array_of_ordered_dict)
```

## Alternative approach to enrich documents

Enrichment can also be achieved with the [enrich processor](https://www.elastic.co/guide/en/elasticsearch/reference/master/ingest-enriching-data.html) which runs in an Elasticsearch [ingest node](https://www.elastic.co/guide/en/elasticsearch/reference/master/ingest.html). The blog titled [Should I use Logstash or Elasticsearch ingest nodes](https://www.elastic.co/blog/should-i-use-logstash-or-elasticsearch-ingest-nodes) may help decide which is the appropriate choice.

## Conclusion

In this blog post I have showed how Logstash can use the translate filter plugin to lookup data for enriching documents. I then showed several different methods of how to populate the translate filter lookup dictionaries. Finally, I presented a script that can be used to convert CSV data into a format that can be used directly by the translate filter plugin.
