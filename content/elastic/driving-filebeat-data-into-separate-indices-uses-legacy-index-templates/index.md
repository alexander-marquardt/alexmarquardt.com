---
title: "Driving Filebeat data into separate indices (uses legacy index templates)"
date: 2021-03-15
slug: driving-filebeat-data-into-separate-indices-uses-legacy-index-templates
aliases: 
  - /2021/03/15/driving-filebeat-data-into-separate-indices-uses-legacy-index-templates/
---

## Introduction

When driving data into [Elasticsearch](https://www.elastic.co/elasticsearch/) from [Filebeat](https://www.elastic.co/guide/en/beats/filebeat/current/filebeat-overview.html), the default behaviour is for all data to be sent into the same destination index regardless of the source of the data. This may not always be desirable since data from different sources may have different access requirements , different retention policies, or different ingest processing requirements.

In this post, we'll use Filebeat to send data from separate sources into multiple indices, and then we'll use [index lifecycle management (ILM)](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html), [_legacy_ index templates](https://www.elastic.co/guide/en/elasticsearch/reference/7.11/indices-templates-v1.html), and a [custom ingest pipeline](https://www.elastic.co/blog/new-way-to-ingest-part-1) to further control that data.

_If you are interested in using the newer [composable templates](https://www.elastic.co/guide/en/elasticsearch/reference/7.11/index-templates.html) and [data streams](https://www.elastic.co/guide/en/elasticsearch/reference/master/data-streams.html) to control your Filebeat data, see the blog [How to manage Elasticsearch data across multiple indices with Filebeat, ILM, and data streams](https://www.elastic.co/blog/how-to-manage-elasticsearch-data-multiple-indices-filebeat-ilm-data-streams)._

## Driving different data types into different destinations

You may have several different types of data that may be collected by filebeat, such as “source1”, “source2”, etc. As these may have different access/security requirements and/or different retention requirements it may be useful to drive data from different sources into different filebeat indices.

_Keep in mind that splitting the filebeat data into different destinations adds complexity to the deployment. For many customers, the default behaviour of driving all filebeat data into a single destination pattern is acceptable and does not require the custom configuration that we outline below._

## Step 1 - Create alias(es)

Each destination "index" that we will specify in Filebeat will actually be an [alias](https://www.elastic.co/guide/en/elasticsearch/reference/7.11/indices-aliases.html) so that [index lifecycle management (ILM)](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html) will work correctly.

We can create an alias that will work with the Filebeat configuration that we give later in this blog, as follows:

```
PUT filebeat-7.10.2-source1-000001
{
  "aliases": {
    "filebeat-7.10.2-source1": {
      "is_write_index": true
    }
  }
}
```

You would want to do the same for other data sources (eg. source2, etc).

In the above alias, by naming the index filebeat-7.10.2-source1, which includes the version number after the word filebeat, we ensure that the default template that is pushed into the cluster by filebeat will be applied to the index.

## Step 2 - Define an ILM policy

You should define the index lifecycle management policy ([see this link](https://www.elastic.co/guide/en/elasticsearch/reference/7.11/getting-started-index-lifecycle-management.html) for instructions).

A single policy can be used by multiple indices, or you can define a new policy for each index. In the next section, I assume that you have created a policy called "filebeat-policy".

## Step 3 - Ensure that ILM will use the correct rollover alias

In order for ILM to automate rolling over of indices, we define the rollover alias that will be used. This can be done by creating a [high-order template](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates-v1.html#put-index-template-v1-api-query-params) (that overwrites the lower-order templates) so that each unique data type will have a unique rollover alias. For example, the following template can be used to ensure that the source1 data rolls over correctly:

```
PUT _template/filebeat-7.10.2-source1-ilm
{
  "order": 50,
  "index_patterns": [
    "filebeat-7.10.2-source1-*"
  ],
  "settings": {
    "index": {
      "lifecycle": {
        "name": "filebeat-policy",
        "rollover_alias": "filebeat-7.10.2-source1"
      }
    }
  }
}
```

## Step 4 - (Optional) Define a custom ingest pipeline

Below is an example of a very simple ingest pipeline that we can use to modify documents that are ingested into Elasticsearch. As we will see in the next section, this can selectively be applied to data from different sources depending on the destination index name.

If the ingest pipeline has a failure in it, then the document that triggered the failure is rejected. This is likely undesirable, and may be enhanced by including on\_failure error handling into the pipeline code as shown below:

```
PUT _ingest/pipeline/my_custom_pipeline
{
  "description": "Put your custom ingest pipeline code here",
  "processors": [
    {
      "set": {
        "field": "my-new-field",
        "value": "some new value",
        "on_failure": [
          {
            "set": {
              "field": "error.message",
              "value": "my_custom_pipeline failed to execute set - {{ _ingest.on_failure_message }}"
            }
          }
        ]
      }
    }
  ],
  "on_failure": [
    {
      "set": {
        "field": "error.message",
        "value": "Uncaught failure in my_custom_pipeline: {{ _ingest.on_failure_message }}"
      }
    }
  ]
}
```

## Step 5 - (Optional) Execution of the custom ingest pipeline

The following template will ensure that our ingest pipeline will be executed against all documents arriving to indices that match the specified index patterns.

Be sure to modify the index patterns below to include all of the index names that should have our custom pipeline applied.

```
PUT _template/filebeat-template-to-call-my-custom-processors
{
  "order": 51,
  "index_patterns": [
    "filebeat-*-source1-*",
    "filebeat-*-source2-*"
  ],
  "settings": {
    "index": {
      "final_pipeline": "my_custom_pipeline"
    }
  },
  "mappings": {},
  "aliases": {}
}

```

Notice that we have used [final\_pipeline](https://www.elastic.co/guide/en/elasticsearch/reference/master/index-modules.html#dynamic-index-settings) rather than [default\_pipeline](https://www.elastic.co/guide/en/elasticsearch/reference/master/index-modules.html#dynamic-index-settings). This is to ensure that calling our custom pipeline does not override any of the default Filebeat pipelines that may be called by various Filebeat modules.

## Step 6 - Filebeat code to drive data into different destination indices

The following filebeat code can be used as an example of how to drive documents into different destination index aliases. Note that if the alias does not exist, then filebeat will create an index with the specified name rather than driving into an alias with the specified name, which is undesirable. Therefore, defining the alias as shown in Step 1 of this blog should be done before running filebeat with this configuration.

The example below would drive data into an alias (or index) called filebeat-7.10.2-source1 (assuming we are running Filebeat version 7.10.2).

```
filebeat.inputs:
- type: log
 enabled: true
 paths:
   - /tmp/<path to your input>.txt
 fields_under_root: true
 fields:
   data_type: "source1"

setup.template.enabled: true
setup.template.name: "filebeat-%{[agent.version]}"
setup.template.pattern: "filebeat-%{[agent.version]}-*"
setup.template.fields: "fields.yml"
setup.template.overwrite: false
setup.ilm.enabled: false # we handle ILM in the cluster, so not defined here

output.elasticsearch:
 hosts: ["localhost:9200"]
 indices:
   - index: "filebeat-%{[agent.version]}-%{[data_type]}"

```

In the above example, there are several setup.template settings which will ensure that the default filebeat templates are loaded correctly into the cluster if they do not already exist. See [configure elasticsearch index template loading](https://www.elastic.co/guide/en/beats/filebeat/current/configuration-template.html) for more information.

## Upgrading filebeat

Once you have implemented the above, then when upgrading to a new version of filebeat you will have to ensure that a new index alias is pointing to the correct underlying indices (re-execute step 1), and that ILM will use the correct alias (re-execute step 3). If these steps are done, then the new version of filebeat should be able to execute the same filebeat.yml that we have defined above in step 6 without modification.

## Appendix 1 - code for testing the ingest pipeline  

The pipeline below will send two documents into the pipeline given in Step 4. This can be used for validating that the pipeline is behaving as expected.

```
POST _ingest/pipeline/my_custom_pipeline/_simulate
{
  "docs": [
    {
      "_source": {
        "message": "this is doc 1"
      }
    },
    {
      "_source": {
        "message": "this is doc 2"
      }
    }
  ]
}
```

## Conclusion

In this post, I showed how to use Filebeat to send data from separate sources into multiple indices, and how to use index lifecycle management (ILM), [_legacy_ index templates](https://www.elastic.co/guide/en/elasticsearch/reference/7.11/indices-templates-v1.html), and a [custom ingest pipeline](https://www.elastic.co/blog/new-way-to-ingest-part-1) to further control that data.
