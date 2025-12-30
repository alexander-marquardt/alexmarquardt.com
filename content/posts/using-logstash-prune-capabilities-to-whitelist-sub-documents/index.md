---
title: "Using Logstash prune capabilities to whitelist sub-documents"
date: 2018-08-28
categories: 
  - "elasticsearch"
tags: 
  - "etl"
  - "logstash"
---

# Overview

Logstash's [prune filter plugin](https://www.elastic.co/guide/en/logstash/current/plugins-filters-prune.html) can make use of whitelists to ensure that only specific desired fields are output from Logstash, and that all other fields are dropped. In this blog post we demonstrate the use of Logstash to whitelist desired fields and desired sub-documents before indexing into Elasticsearch.

# Example input file

As an input to Logstash, we use a CSV file that contains stock market trades. A few example CSV stock market trades are given below. 

```
1483230600,1628.75,1678.1,1772.8,2443.6
1483232400,1613.63,1688.5,1750.5,2460.2
1483234200,1606.51,1678.6,1718,2448.2
1483236000,1621.04,1684.1,1708.1,2470.4
```

The comma separated values represent  "time", "DAX", "SMI", "CAC", "FTSE" . You may wish to copy and paste the above lines into a CSV file called stocks.csv in order to execute the example command line given later in this blogpost. 

# Example Logstash pipeline

Below is a Logstash pipeline which can be stored in a file called 'stocks.conf', that does the following:

1. Reads stock market trades as CSV-formatted input from stdin.
2. Maps each row of the CSV input to a JSON document, where the CSV columns map to JSON fields.
3. Converts the time field to Unix format.
4. Moves DAX and CAC fields into a nested structure called "my\_nest".
5. Whitelists the "my\_nest" field (which contains a sub-document) and the "SMI" field so that all other (non-whitelisted) fields will be removed.
6. Writes the resulting documents to an Elasticsearch index called "stocks\_whitelist\_test".

```
# For this simple example, pipe in data from stdin. 
input {
    stdin {}
}

filter {
    csv {
        columns => ["time","DAX","SMI","CAC","FTSE"]
        separator => ","
        convert => { 'DAX' => 'float'
        'SMI' => 'float'
        'CAC' => 'float'
        'FTSE' => 'float'}
    }
    date {
        match => ['time', 'UNIX']
    }
    mutate {
        # Move DAX and CAC into a sub-document 
        # called 'my_nest'
        rename => {
            "DAX" => "[my_nest][DAX]"
            "CAC" => "[my_nest][CAC]"
        }
    }
     
    # Remove everything except "SMI" and the 
    # "my_nest" sub-document 
    prune {
         whitelist_names => [ "SMI", "my_nest" ]
    }
}

output {
    stdout { codec => dots }
    elasticsearch {
        index => "stocks_whitelist_test"
    }
}
```

# Testing the logstash pipeline

To test this pipeline with the example CSV data, you could execute something similar to the following command, modifying it to ensure that you use paths that are correct for your system:

```
cat ./stocks.csv | ./logstash -f ./stocks.conf
```

You can the check the data that you have stored in Elasticsearch by executing the following comand from Kibana's dev console:

```
GET /stocks_whitelist_test/_search
```

Which should display documents with the following structure:

```
      {
        "_index": "stocks_whitelist_test",
        "_type": "doc",
        "_id": "KANygWUBsYalOV9yOKsD",
        "_score": 1,
        "_source": {
          "my_nest": {
            "CAC": 1718,
            "DAX": 1606.51
          },
          "SMI": 1678.6
        }
      }
```

Notice that only "my\_nest" and "SMI" have been indexed as indicated by the contents of the document's "\_source". Also note that the "FTSE" and "time" fields have been removed as they were not in the prune filter's whitelist.

# Conclusion

In this blog post, we have demonstrated how Logstash’s [prune filter plugin](https://www.elastic.co/guide/en/logstash/current/plugins-filters-prune.html) can make use of whitelists to ensure that only specific desired fields are output from Logstash.
