---
showtoc: true
title: "Automating the Import and Export of Kibana Saved Objects"
date: 2024-05-03
slug: automating-the-import-and-export-of-kibana-saved-objects
aliases:
  - /2024/05/03/automating-the-import-and-export-of-kibana-saved-objects/
---

## Introduction

[Kibana](https://www.elastic.co/guide/en/kibana/current/introduction.html) is an open-source data visualization and exploration tool used for log and time-series analytics, application monitoring, and operational intelligence use cases. It offers powerful and easy-to-use features that allow users to visualize data from Elasticsearch in various formats such as charts, tables, and maps.

While Kibana offers a robust user interface for managing many tasks, certain operations can become tedious and time-consuming when done manually, especially for operations teams managing large and complex environments. One such operation is the migration of Kibana spaces and objects between environments—a task that can be critical in scenarios where clients cannot utilize the [snapshot/restore functionality](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html) provided by Elasticsearch.

## Options for Migrating Kibana from one Environment to Another

Traditionally, moving [Kibana objects](https://www.elastic.co/guide/en/kibana/current/managing-saved-objects.html) (dashboards, visualizations, saved searches, etc.) and spaces between different environments or instances requires either using the [snapshot and restore features](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html) of Elasticsearch or manually [exporting](https://www.elastic.co/guide/en/kibana/current/managing-saved-objects.html#_export) and [importing](https://www.elastic.co/guide/en/kibana/current/managing-saved-objects.html#_import) JSON files through the Kibana UI.

If you can make use of snapshot/restore for migrating [Kibana feature states](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html#feature-state), **that should be the preferred approach**. However, snapshot/restore might not always be available due to various constraints such as corporate security policies or other restrictions. Meanwhile, manual exports and imports are labor-intensive. In this blog, we present a third option - scripts that will automate the import and export of Kibana Saved Objects.

## Scripts available on github

If you would like to automate the process of exporting and importing Kibana objects, you may find the [kibana-import-export repository on github](https://github.com/alexander-marquardt/kibana-import-export) to be useful.  
  
This repository has two simple to use scripts: 'export\_kibana.py' which extracts your Kibana objects from all of your Kibana spaces to a local file. And 'import\_kibana.py' which can be used to recreate the extracted Kibana spaces and objects on a different Kibana instance.

These scripts make use of the the following APIs:

- [Get all Kibana spaces API](https://www.elastic.co/guide/en/kibana/current/spaces-api-get-all.html)

- [Export objects API](https://www.elastic.co/guide/en/kibana/current/saved-objects-api-export.html)

- [Create space API](https://www.elastic.co/guide/en/kibana/current/spaces-api-post.html)

- [Import objects API](https://www.elastic.co/guide/en/kibana/current/saved-objects-api-import.html).

After downloading the scripts from [https://github.com/alexander-marquardt/kibana-import-export](https://github.com/alexander-marquardt/kibana-import-export), type the following commands to get information about the command line parameters that are available:

- export\_kibana.py -h

- import\_kibana.py -h

## Disclaimer and Usage Notes

- **Use at Your Own Risk**: These scripts are provided as is, without warranty of any kind. Users should use the scripts at their own risk.

- **Validation Required**: Always validate the script in a realistic test environment before applying it on production systems. This ensures that any unforeseen errors can be caught and corrected in a safe manner.

- **Intended Use**: These scripts are generally intended for setting up a new system to which you are migrating, and which is empty. The default setting in the import script is to overwrite existing Kibana objects in the destination. If the destination system is not empty and you wish to preserve existing objects, you should modify the command line parameters.

## Conclusion

For Kibana users unable to leverage snapshot/restore, these scripts for exporting and importing spaces are a feasible alternative.
