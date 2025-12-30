---
title: "Understanding and fixing \"too many script compilations\" errors in Elasticsearch"
date: 2020-10-21
categories: 
  - "elasticsearch"
slug: elasticsearch-too-many-script-compilations
aliases:
  - /2020/10/21/elasticsearch-too-many-script-compilations/
---

## Introduction

When using Elasticsearch, in some rare instances you may see an error such as "Too many dynamic script compilations within X minutes". Such an error may be caused by a poor script design [where parameters are hard-coded](https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-scripting-using.html#prefer-params). In other cases this may be due to the script cache being too small or the compilation limit being too low. In this article, I will show how to determine if these default limits are too low, and how these limits can be modified.

## Warning

In this blog I will show you how to change default settings used for caching scripts Elasticsearch. Changing these to very large values may impact cluster performance and in the worst case could even cause your cluster to crash.

## Script caching

Scripts are cached by default so that they only need to be recompiled when updates occur. However, as these scripts are stored in a _cache_, if the cache gets filled up, then some of the previously compiled scripts will be removed from the cache and would need to be recompiled again if they are needed in the future. For more information, see the documentation on [script caching](https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-scripting-using.html#modules-scripting-using-caching).

## Deprecated script settings (Read this if you are running 7.8 or earlier)

Versions of Elasticsearch 7.8 and earlier [will compile up to 15 inline scripts per minute](https://www.elastic.co/guide/en/elasticsearch/reference/7.8/modules-scripting-using.html#_script_parameters). These compiled scripts are then stored in the script cache which by default [can store up to 100 scripts](https://www.elastic.co/guide/en/elasticsearch/reference/7.8/modules-scripting-using.html#modules-scripting-using-caching).

The statistics for the script cache can be viewed with the following command:

```
GET /_nodes/stats?metric=script&filter_path=nodes.*.script.* 
```

Which should respond with something similar to the following:

```
{
  "nodes" : {
    "XfXvXJ7xSLynbdZBsFwG3A" : {
      "script" : {
        "compilations" : 28,
        "cache_evictions" : 0,
        "compilation_limit_triggered" : 0
      }
    },
    "pzrnXnehTrKEN0urD7j9eg" : {
      "script" : {
        "compilations" : 407081,
        "cache_evictions" : 406981,
        "compilation_limit_triggered" : 5176579
      }
    }
    ... etc ...
```

The numbers shown are counted since the last restart of each node. If the `compilations` and `cache_evictions` have large numbers or are constantly increasing, this may indicate that the cache is churning, and may therefore indicate that the cache is too small.

A high value for `compilation_limit_triggered` may be a side effect of having a cache that is too small, or possibly poor script design [where parameters are hard-coded](https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-scripting-using.html#prefer-params) .

The script cache may be configured by setting `script.cache.max_size` in the `elasticsearch.yml` configuration file as follows.

```
script.cache.max_size: 300
```

And you can dynamically set `script.max_compilations_rate` as follows:

```
PUT _cluster/settings
{
  "persistent": {
    "script.max_compilations_rate": "250/5m"
  }
}
```

However both of these settings are  [now deprecated](https://www.elastic.co/guide/en/elasticsearch/reference/current/breaking-changes-7.9.html#breaking_79_script_cache_changes).

## Script settings in Elasticsearch 7.9 and newer

Starting in Elasticsearch 7.9, by default scripts are stored depending on the contexts which they execute in. Contexts allow different defaults to be set for different kinds of scripts that Elasticsearch may execute. There are many contexts available, such as "watcher\_transform", "bucket aggregation", "aggs\_combine", and many others. For those adventurous enough to look in the source code, instantiation of contexts can be seen with [this search on GitHub](https://github.com/elastic/elasticsearch/search?p=1&q=%22new+ScriptContext%22).

Contexts are enabled by default starting in 7.9. However, if contexts (for some reason) are not currently enabled, they can be enabled with the following command:

```
PUT _cluster/settings
{
    "persistent": {
        "script.max_compilations_rate": "use-context"
    }
}
```

If contexts are used, they can be viewed with the following command:

```
GET /_nodes/stats?filter_path=nodes.*.script_cache.contexts
```

This should respond with a list of the contexts that are used for executing scripts, such as the following:

```
    {
        "nodes" : {
          "lqxteGihTpifU5lvV7BEmg" : {
            "script_cache" : {
            "contexts" : [
                {
                    "context" : "aggregation_selector",
                    "compilations" : 1,
                    "cache_evictions" : 0,
                    "compilation_limit_triggered" : 0
                }

                 ... etc ...
        
                {
                   "context" : "xpack_template",
                   "compilations" : 0,
                   "cache_evictions" : 0,
                   "compilation_limit_triggered" : 0
                 }
            
                 .... etc ...

```

If the response above is empty, then "use-context" may not be enabled, and can be enabled as described above.

As with previous versions of Elasticsearch, if the `compilations` and `cache_evictions` have large numbers or are constantly increasing, this may indicate that the cache is churning, and may be an indicator that the cache is too small.

For most contexts, you can compile up to 75 scripts per 5 minutes by default. For ingest contexts, the default script compilation rate is unlimited. For most contexts, the default cache size is 100. For ingest contexts, the default cache size is 200. These defaults are given in the [7.9 documentation on how to use scripts](https://www.elastic.co/guide/en/elasticsearch/reference/7.9/modules-scripting-using.html#prefer-params).

You can set `script.context.$CONTEXT.cache_max_size` in the `elasticsearch.yml` configuration file. For example, to set the max size for the `xpack_template` context, you would add the following to `elasticsearch.yml`.

```
script.context.xpack_template.cache_max_size: 300
```

On the other hand,`script.context.$CONTEXT.max_compilations_rate` may be set dynamically. For example you can configure the compilations rate for the `xpack_template` context as follows:

```
PUT _cluster/settings
{
    "persistent": {
        "script.context.xpack_template.max_compilations_rate": "150/5m"
    }
}
```

## Conclusion

In this blog, I have shown how you can look deeper into Elasticsearch to try to diagnose the potential cause of script compilation errors, and how to modify default settings if necessary.

## Acknowledgement

Thanks to my Elastic colleague Michael Bischoff for providing guidance on how to investigate and fix the "too many script compilations within X minutes" issue.
