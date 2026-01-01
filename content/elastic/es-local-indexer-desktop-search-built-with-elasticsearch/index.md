---
title: "ES Local Indexer – Desktop search powered by Elasticsearch"
date: 2019-08-08
slug: es-local-indexer-desktop-search-built-with-elasticsearch
aliases:
  - /es-local-indexer-desktop-search-built-with-elasticsearch/
  - /es-local-indexer-using-elasticsearch-for-searching-locally-stored-documents/
---

# Introduction

Elasticsearch provides search functionality for some of the most important websites in the world including [Wikimedia (i.e. Wikipedia)](https://blog.wikimedia.org/2014/01/06/wikimedia-moving-to-elasticsearch/), [eBay](https://www.elastic.co/videos/ebay-and-elasticsearch-this-is-not-small-data), [Yelp](https://engineeringblog.yelp.com/2017/06/moving-yelps-core-business-search-to-elasticsearch.html), [Tinder](https://www.elastic.co/elasticon/conf/2017/sf/tinder-using-the-elastic-stack-to-make-connections-around-the-world), and many others. Elasticsearch is super scalable, which means that just as easily as it can be scaled it up for use in huge complex systems, it can also be scaled down for use in smaller projects.

[ES Local Indexer](https://github.com/alexander-marquardt/es_local_indexer) is a small desktop search application that runs on top of a local Elasticsearch installation. It indexes HTML documents into Elasticsearch and provides an intuitive browser-based interface for searching through the ingested documents. The ES Local Indexer project consists of two main components:

1. An indexing app - indexes all documents in a given directory tree into Elasticsearch.
2. A searching app - generates and displays the search results.

ES Local Indexer is simple to use. In order to ingest HTML documents into Elasticsearch and then search them, just start a local instance of Elasticsearch, ingest data into Elasticsearch with the indexing app, and then start the searching app. After starting the searching app, use a browser to view the search results.

# Purpose

The ES Local Indexer project is intended for the following scenarios:

- It can be used as a reference for implementing search functionality within a larger project or as a base for implementing a full-featured search application.
- It can be used for indexing previously downloaded html documents, and providing search capabilities across those documents. This could be useful for example if one knows they will not have internet access for some amount of time (such as while on an airplane), and need to be able to search previously downloaded documents.

ES Local Indexer is not fully-featured or production-ready and is designed to be used locally (i.e. not exposed to the internet). In order to keep the code simple I have not used any Javascript or CSS on the front end. A production application based on this code would likely add both CSS and Javascript to improve the user experience.

# Requirements and Installation

See the [ES Local Indexer gitub page](https://github.com/alexander-marquardt/es_local_indexer) for installation instructions.

# Ingesting local documents data into Elasticsearch

To test ES Local Indexer with real documents, download offline Elasticsearch documentation in HTML form from [https://github.com/elastic/built-docs](https://github.com/elastic/built-docs). Once downloaded, the HTML documents are ready for ingestion into Elasticsearch.

In order to ingest the HTML documents, execute the following command replacing PATH\_TO\_DOCS with the path to the documentation directory, and INDEX\_NAME with the name of the Elasticsearch index that will ingest the HTML from each page:

```
python3 indexing_app.py -p PATH_TO_DOCS -i INDEX_NAME

```

In my environment, the exact command that I enter to ingest the HTML Documentation into Elasticsearch is the following:

```
python3 indexing_app.py -p ~/Documents/built-docs/ -i built_es_docs_idx
```

Once the ingestion process has started, move on to the next step (although search results will be more meaningful ingestion has completed).

# [](https://github.com/alexander-marquardt/es_local_indexer/blob/master/README.md#searching-local-documents)Launch the search application

Once documents have been ingested into Elasticsearch, the code to launch the search interface web app can be executed as follows:

```
python3 searching_app.py -p PATH_TO_DOCS -i INDEX_NAME

```

The PATH\_TO\_DOCS and INDEX\_NAME should be the same as the values specified when ingesting the documents into Elasticsearch. In my environment, the exact command to launch the search interface web app is the following:

```
 python3 searching_app.py -p ~/Documents/built-docs/ -i built_es_docs_idx
```

Point a browser to [http://127.0.0.1:5000/](http://127.0.0.1:5000/), and begin searching the documents that were previously downloaded and indexed into Elasticsearch.

# Using the search application

The search interface is designed to mimic popular search applications such as Google or Bing.  The main search page appears as follows:

![Screenshot 2019-08-07 at 22.02.00](images/screenshot-2019-08-07-at-22.02.00.png)

After hitting the search button, results will appear as follows:

![Screenshot 2019-08-07 at 22.02.56.png](images/screenshot-2019-08-07-at-22.02.56.png)

Notice that in the above results it appears that the first three hits are identical. This is because we have ingested basically the same document three times - _current_, _7.3_, and _master_ \- each of which contains the same information, and so it is not surprising that we have three hits each with the same _score_. We get better results if we include the version in our search request as follows:

![Screenshot 2019-08-07 at 22.06.21.png](images/screenshot-2019-08-07-at-22.06.21.png)

Now the first three documents are different and they all correspond to documentation for version 7.3 of Elasticsearch. While this is much better than before, it could be made even better by taking advantage of domain-specific knowledge that we have with respect to Elasticsearch documentation. If this were an application that were designed for _only_ displaying Elasticsearch documentation, it would make sense to:

1. Ensure that a "version" field is created when each document is indexed into Elasticsearch.
2. Include a drop-down menu to allow the user to select which version of documentation they are interested in seeing.
3. Filter documents for a specific version by using a [bool filter](https://www.elastic.co/guide/en/elasticsearch/reference/7.3/query-dsl-bool-query.html#score-bool-filter) to ensure that all documents that do not match the desired release are filtered out and not displayed.

However, we have not implemented the above domain-specific enhancements because ES Local Indexer is designed to be a _generic_ implementation.

# Conclusion

In this blog we have presented ES Local Indexer. This is a desktop search application that provides capabilities to ingest HTML documents from a local source into Elasticsearch, and that displays a web-based interface for searching these documents. ES Local Indexer can be used for searching downloaded HTML content, or it can be used as a base for larger projects that require search functionality.
