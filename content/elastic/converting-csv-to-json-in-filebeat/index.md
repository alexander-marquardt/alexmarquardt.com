---
showtoc: true
title: "Converting CSV to JSON in Filebeat"
date: 2020-03-17
slug: converting-csv-to-json-in-filebeat/
aliases:
  - /2020/03/17/converting-csv-to-json-in-filebeat/
---

## Introduction

Many organisations use excel files for creating and storing important data. For various reasons it may be useful to import such data into Elasticsearch. For example, one may need to get [Master Data](https://en.wikipedia.org/wiki/Master_data) that is created in a spreadsheet into Elasticsearch where it could be used for [enriching Elasticsearch documents](https://www.elastic.co/guide/en/elasticsearch/reference/7.x/ingest-enriching-data.html). Or one may wish to use Elasticsearch and Kibana for analysing a dataset that is only available in a spreadsheet. In such cases, one option is to use [Filebeat](https://www.elastic.co/guide/en/beats/filebeat/7.6/filebeat-overview.html) for uploading such CSV data into an Elasticsearch cluster.

In this blog I will show how Filebeat can be used to convert CSV data into JSON-formatted data that can be sent into an Elasticsearch cluster. This will be accomplished by using a built-in CSV processor as well as a custom JavaScript processor which will be applied to every line in a CSV file.

Note that Filebeat is intended for sending log lines into Elasticsearch. On the other hand, the technique described in this blog is _not intended_ to run on a CSV file that continually has lines added to it.  The technique and code presented in this article is intended for ingesting an existing CSV file a single time, and it then terminates Filebeat immediately after the file has been ingested.

## Motivation

Filebeat supports a [CSV processor](https://www.elastic.co/guide/en/beats/filebeat/7.6/decode-csv-fields.html) which extracts values from a CSV string, and stores the result in an array. However, this processor does not create key-value pairs to maintain the relation between the column names and the extracted values. When using the CSV processor, additional processing (and hard-coding of the field names) is generally required in an [ingest node](https://www.elastic.co/guide/en/elasticsearch/reference/7.6/ingest.html) or in [Logstash](https://www.elastic.co/guide/en/logstash/7.6/introduction.html) to add the correct field names back into the extracted data.

On the other hand, the approach presented in this blog will automatically extract field names from the CSV header, and then generate key-value pairs based on each row’s values combined with the field names that are extracted from the header row. This technique therefore eliminates the need for additional ingest node or Logstash processing that would otherwise be required.

## Code

All code presented in this blog is available at: [https://github.com/alexander-marquardt/filebeat-csv-to-json](https://github.com/alexander-marquardt/filebeat-csv-to-json)

## A note on the Filebeat registry

Because Filebeat is designed for sending log lines from files which are actively being written, it keeps track of the most recent log entry that it has sent to Elasticsearch, and ensures that each entry is only sent once. This is tracked in the [Filebeat registry](https://www.elastic.co/guide/en/beats/filebeat/7.6/configuration-general-options.html). We should be aware the existence of the registry, as the registry will prevent sending the same CSV data to Elasticsearch multiple times, which can be undesirable when testing.

## A note on Filebeat processors

[Processors](https://www.elastic.co/guide/en/beats/filebeat/current/filtering-and-enhancing-data.html) are executed on data as it passes through Filebeat. The code presented in this blog makes use of the [CSV processor](https://www.elastic.co/guide/en/beats/filebeat/7.6/decode-csv-fields.html) as well as a custom [script processor](https://www.elastic.co/guide/en/beats/filebeat/current/processor-script.html). The custom script processor will apply custom JavaScript code to each event (in our case, to each to CSV line), which converts the CSV values into key-value pairs in a JSON object.

## Example CSV input

We will store the following data in a file called _test.csv._ This file will be used to show how CSV can be converted into JSON. This CSV is intentionally written in an inconsistent format, to ensure that the code is working correctly for different formats:

```
first_col,col2,col3,fourth_col
1234,"first 1",123,third 1
5678,first 2,456,"third 2"
```

## Filebeat configuration

We use the following _filebeat.yml_ configuration to call the CSV processor as well as our custom JavaScript.

```
max_procs: 1 # This code will not work correctly on multiple threads
 
filebeat.inputs:
- type: log
  enabled: true
  close_eof: true
  paths:
    - ${PWD}/test.csv

  processors:
  - decode_csv_fields:
      fields:
        message: decoded_csv_arr
      separator: ","
      ignore_missing: false
      overwrite_keys: true
      trim_leading_space: false
      fail_on_error: true

  - script:
      lang: javascript
      id: convert_csv_into_json
      file: ${PWD}/convert_csv_to_json.js

  - drop_fields:
      fields: ["decoded_csv_arr"]

output.elasticsearch:
  hosts: ["localhost:9200"]

  index: "csv_to_json-%{+YYYY.MM.dd}" 

setup.ilm.enabled: false
setup.template.enabled: false
```

## JavaScript processor code

Below we present the JavaScript code that we use for converting lines in a CSV file into JSON objects. This should be stored in a file called _convert\_csv\_to\_json.js_ which is referenced in the _filebeat.yml_ configuration that we presented above.

When the first line of CSV is passed into this JavaScript processor, the code uses a [JavaScript closure](https://www.w3schools.com/js/js_function_closures.asp) to “remember” the header values. When subsequent lines from the CSV file are passed in, the headers are combined with the values in each row to create key-value pairs that are stored in a JSON object.

Note that this will only work as a single threaded process since the closure containing the header fields is only available in the thread that processes the header row. This is ensured by setting _max\_procs: 1_ in _filebeat.yml_.

```
// This function takes an array containing the field names, and another that
// contains field values, and returns a json dictionary that combines them.
function convert_csv_to_dict(csv_headers_row, csv_values_row) {
  var json_from_csv =  csv_values_row.reduce(function(result, field, index) {
    result[csv_headers_row[index]] = field;
    return result;
  }, {})

  return json_from_csv;
}

// Define the JavaScript function that will be used to combine the 
// header row with subsequent rows in the CSV file
var headers_fn = (function() {
  var csv_headers_row = null; 

  // Use a JavaScript closure to store the header line (csv_headers_row), 
  // so that we can use the header values for all subsequent CSV entries. 
  return function(csv_arr) {

    var json_from_csv = null;

    if (!csv_headers_row) {
      // if this is the first row, store the headers
      csv_headers_row = csv_arr;
    } else {
      // combine the csv_headers_row with the values to get a dict
      json_from_csv = convert_csv_to_dict(csv_headers_row, csv_arr)
    }
    return json_from_csv;
  }

})();  

// This function is called for each "event" 
// (eg. called once for each line in the log file)
function process(event) {
    var csv_arr = event.Get("decoded_csv_arr");
    var json_from_csv = headers_fn(csv_arr);

    // If the current event was triggered to process the header row,
    // then the json_from_csv will be empty - it only returns a json dict
    // for subsequent rows. Cancel the event so that nothing
    // is sent to the output.
    if (!json_from_csv) {
      event.Cancel();
    }
    event.Put("json_from_csv", json_from_csv);
}
```

## Executing the code

The following command line can be used for executing the code which converts the CSV into JSON, and then sends the resulting documents into Elasticsearch.

```
rm -rf my_reg; ./filebeat  -once -E filebeat.registry.path=${PWD}/my_reg
```

There are a few things to point out about this command line.

1. It deletes the registry directory before executing filebeat. This means that the input file will be sent each time that Filebeat is executed. To prevent multiple copies of the same document from appearing in the destination index, the destination index should be deleted before running this code.
2. It is storing the registry in the local directory, which makes it easier to find and delete it.
3. It is running with the “-once” option, which makes filebeat exit once the command has completed.

## Results

Once the above code has executed, there should be an index written into Elasticsearch that starts with "csv\_to\_json-". Looking into this index, we can see that the documents contain the following field, which has been extracted from the CSV file.

```
"json_from_csv" : {
  "col3" : "123",
  "fourth_col" : "third 1",
  "first_col" : "1234",
  "col2" : "first 1"
}
```

## Conclusion

In this blog, I have shown how filebeat can be used to convert CSV data into JSON objects in the documents that are sent to Elasticsearch. Because the field names in the JSON object are extracted directly from the CSV file, this technique eliminates the need for either ingest nodes or Logstash which would otherwise be required for adding the correct field names to the CSV data.
