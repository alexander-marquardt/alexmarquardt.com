---
showtoc: true
title: "Using Elasticsearch Painless scripting to recursively iterate through JSON fields"
date: 2020-11-06
slug: using-elasticsearch-painless-scripting-to-iterate-through-fields
aliases:
  - /2020/11/06/using-elasticsearch-painless-scripting-to-iterate-through-fields/
---

## Authors

- Alexander Marquardt
- Honza Kral

## Introduction

_[Painless](https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-scripting-painless.html)_ is a simple, secure scripting language designed specifically for use with Elasticsearch. It is the default scripting language for Elasticsearch and can safely be used for inline and stored scripts. In one of its many use cases, Painless can modify documents as they are ingested into your Elasticsearch cluster. In this use case, you may find that you would like to use Painless to evaluate every field in each document that is received by Elasticsearch. However, because of the hierarchical nature of JSON documents, how to iterate over all of the fields may be non-obvious.

This blog provides examples that demonstrate how Painless can iterate across all fields in each document that Elasticsearch receives, regardless of wheather fields appear directly in the top-level JSON body, or if they are contained in sub-documents or arrays.

## Example one - remove empty fields

The following painless script called "remove\_empty\_fields" shows how to loop over all elements in a document, and deletes each field where the value is an empty string.

```
PUT _ingest/pipeline/remove_empty_fields
 {
   "processors": [
     {
       "script": {
         "lang": "painless",
         "source": """

           void iterateAllFields(def x) {
             if (x instanceof List) {
               for (def v: x) {
                 iterateAllFields(v);
               }
             }
             if (!(x instanceof Map)) {
               return;
             }
             x.entrySet().removeIf(e -> e.getValue() == "");
             for (def v: x.values()) {
               iterateAllFields(v);
             }
           }

           iterateAllFields(ctx);
       """
       }
     }
   ]
 }
```

Notice that we use [removeIf](https://docs.oracle.com/javase/8/docs/api/java/util/Collection.html#removeIf-java.util.function.Predicate-) in the above code, which will correctly remove fields with an empty string as a value. Using a more naive approach with a for loop to iterate over the fields returned by "x.entrySet()" and then executing [remove](https://docs.oracle.com/javase/8/docs/api/java/util/Collection.html#remove-java.lang.Object-) statement within the for loop to directly delete an element will result in a "ConcurrentModfiicationException", as you cannot modify the Map as it is being looped over.

We can test the above script with the following call to the [simulate pipeline API](https://www.elastic.co/guide/en/elasticsearch/reference/master/simulate-pipeline-api.html) as follows.

```
POST _ingest/pipeline/remove_empty_fields/_simulate
 {
   "docs": [
     {
       "_source": {
         "key1": "first value",
         "key2": "some other value",
         "key3": "",
         "sudoc": {
           "a": "abc",
           "b": ""
         }
       }
     },
     {
       "_source": {
         "key1": "",
         "key2": "some other value",
         "list_of_docs": [
           {
             "foo": "abc",
             "bar": ""
           },
           {
             "baz": "",
             "subdoc_in_list": {"child1": "xxx", "child2": ""}
           }
         ]
       }
     }
   ]
 }
```

Which will return the following results, where each field that contains an empty string has been removed.

```
{
   "docs" : [
     {
       "doc" : {
         "_index" : "_index",
         "_type" : "_doc",
         "_id" : "_id",
         "_source" : {
           "key1" : "first value",
           "key2" : "some other value",
           "sudoc" : {
             "a" : "abc"
           }
         },
         "_ingest" : {
           "timestamp" : "2020-11-06T10:59:29.105406Z"
         }
       }
     },
     {
       "doc" : {
         "_index" : "_index",
         "_type" : "_doc",
         "_id" : "_id",
         "_source" : {
           "list_of_docs" : [
             {
               "foo" : "abc"
             },
             {
               "subdoc_in_list" : {
                 "child1" : "xxx"
               }
             }
           ],
           "key2" : "some other value"
         },
         "_ingest" : {
           "timestamp" : "2020-11-06T10:59:29.105411Z"
         }
       }
     }
   ]
 }
```

## Example two - remove fields where the field name matches a regular expression

The following painless script called "remove\_unwanted\_keys" shows how you can remove keys with a name that match a regular expression. In this example, we delete any fields where the field name starts with "unwanted\_key\_".

Note that by default regexes are disabled. To load this script you will first need to set "script.painless.regex.enabled" to "true" in "elasticsearch.yml".

```
PUT _ingest/pipeline/remove_unwanted_keys
 {
   "processors": [
     {
       "script": {
         "lang": "painless",
         "source": """

           void iterateAllFields(def x) {
             if (x instanceof List) {
               for (def v: x) {
                 iterateAllFields(v);
               }
             }
             if (!(x instanceof Map)) {
               return;
             }
             x.entrySet().removeIf(e -> e.getKey() =~ /unwanted_key_.*/);
             for (def v: x.values()) {
               iterateAllFields(v);
             }
           }

           iterateAllFields(ctx);
       """
       }
     }
   ]
 }

```

We can then test the above script with the following call to the [simulate pipeline API](https://www.elastic.co/guide/en/elasticsearch/reference/master/simulate-pipeline-api.html) as follows.

```
POST _ingest/pipeline/remove_unwanted_keys/_simulate
 {
   "docs": [
     {
       "_source": {
         "key1": "first value",
         "key2": "some other value",
         "key3": "",
         "unwanted_key_something": "get rid of this",
         "unwanted_key_2": "this too",
         "sudoc": {
           "foo": "abc",
           "bar": ""
         }
       }
     }
   ]
 }
```

Which will return the following results, where each field name that started with "unwanted\_key\_" has been removed.

```
{
   "docs" : [
     {
       "doc" : {
         "_index" : "_index",
         "_type" : "_doc",
         "_id" : "_id",
         "_source" : {
           "key1" : "first value",
           "key2" : "some other value",
           "key3" : "",
           "sudoc" : {
             "bar" : "",
             "foo" : "abc"
           }
         },
         "_ingest" : {
           "timestamp" : "2020-11-06T11:19:56.839119Z"
         }
       }
     }
   ]
 }
```

## Conclusion

In this blog we have presented two examples of how all elements in a JSON document can be iterated over, regardless of if they are included in the top-level JSON, or within sub-documents or arrays.
