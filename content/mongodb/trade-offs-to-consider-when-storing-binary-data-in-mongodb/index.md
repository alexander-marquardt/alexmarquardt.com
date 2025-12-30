---
title: "Trade-offs to consider when storing binary data in MongoDB"
date: 2017-03-02
categories: 
  - "mongodb"
tags: 
  - "binary-data"
slug: trade-offs-to-consider-when-storing-binary-data-in-mongodb/
aliases: 
  - /2017/03/02/trade-offs-to-consider-when-storing-binary-data-in-mongodb/
---

# Introduction

When using MongoDB there are several approaches that make it easy to store and retrieve binary data, but it is not always clear which approach is the most appropriate for a given application. Therefore, in this blog post I discuss several methods for storing binary data when using MongoDB and the trade-offs associated with each method. Many of the trade-offs discussed here would likely apply to most other databases as well.

# Overview

In this blog post, I cover the following topics:

- Definition of binary data
- Methods for storing binary data with MongoDB
- General trade-offs to consider when storing binary data in MongoDB
- Considerations for embedding binary data inside individual MongoDB documents (where each binary object fits completely within the 16MB per-document size limit)
- Considerations for storing binary data in MongoDB with GridFS (spreading the binary data across multiple MongoDB documents)
- Considerations for storing binary data outside of MongoDB
- Mitigating some of the drawbacks of storing binary data in MongoDB
- Conclusion

# Definition of binary data

While everything in a computer is technically stored as binary data, in the context of this posting when I refer to Binary Data I am referring to unstructured [BLOB](https://en.wikipedia.org/wiki/Binary_large_object) data such as PDF documents or Jpeg images. This is in contrast to structured data such as text or integers.

# Methods for storing binary data with MongoDB

### Embed binary data in MongoDB documents using the BSON BinData type

MongoDB enforces a [limit of 16MB per document](https://docs.mongodb.com/manual/reference/limits/#BSON-Document-Size), and so if binary data plus other fields in a document are guaranteed to be less than 16MB, then binary data can be embedded into documents by using the BinData [BSON](https://docs.mongodb.com/v3.2/reference/bson-types/) type. For more information using the BinData type, see the documentation for the appropriate [driver](https://docs.mongodb.com/manual/applications/drivers/).

### Store binary data in MongoDB using GridFS

[GridFS](https://docs.mongodb.com/manual/core/gridfs/#when-to-use-gridfs) is a [specification](https://github.com/mongodb/specifications/blob/master/source/gridfs/gridfs-spec.rst) for storing and retrieving files that exceed the BSON document size limit of 16MB. Instead of storing a file in a single document, GridFS divides the file into chunks, and stores each chunk as a separate document. GridFS uses two collections to store files, where one collection stores the file chunks, and the other stores file metadata as well as optional application-specific fields.

An excellent two-part blog post ([part 1](https://www.mongodb.com/blog/post/building-mongodb-applications-binary-files-using-gridfs-part-1) and [part 2](https://www.mongodb.com/blog/post/building-mongodb-applications-binary-files-using-gridfs-part-2)) gives a good overview of how GridFS works, and examples of when GridFS would be an appropriate storage choice.

### Store binary data in an external system, and use MongoDB to store the location of the binary data

Data may be stored outside of the database, for example in a file system. The document in the database could then contain all the required information to know where to look for the associated binary data (a key, a file name, etc.), and it could also store metadata associated with the binary data.

# General trade-offs to consider when storing binary data in MongoDB

### Benefits of storing binary data in MongoDB

- MongoDB provides high availability and replication of data.
- A single system for all types of data results in a simpler application architecture.
- When using [geographically distributed replica sets](https://docs.mongodb.com/manual/core/replica-set-architecture-geographically-distributed/), MongoDB will automatically distribute data to geographically distinct data centres.
- Storing data in the database takes advantage of MongoDB authentication and security mechanisms.

### Drawbacks of storing binary data in MongoDB

- In a [replica set](https://docs.mongodb.com/manual/replication/) deployment, data that is stored in the database will be replicated  to multiple servers, which uses more storage space and bandwidth than a single copy of the data would require.
- If the binary data is large, then loading the binary data into memory may cause frequently accessed text (structured data) documents to be pushed out of memory, or more generally, the [working set](https://docs.mongodb.com/v3.2/faq/diagnostics/#what-is-a-working-set) might not fit into RAM. This can negatively impact the performance of the database.
- If binary data is stored in the database, then most backup methods will back up the binary data at the same frequency as all of the other data in the database. However, if binary data rarely changes then it might be desirable to back it up at a lower frequency than the rest of the data.
- Storing binary data in the database will make the database larger than it would otherwise be, and if a sharded environment is deployed, this may cause balancing between shards to take more time and to be more resource intensive.
- Backups of a database containing binary data will require more resources and storage than backups of a database without binary data.
- Binary data is likely already compressed, and therefore will not gain much benefit from WiredTiger’s compression algorithms.

# Considerations for embedding binary data in MongoDB documents

MongoDB has a [limit of 16MB per document.](https://docs.mongodb.com/manual/reference/limits/#BSON-Document-Size) If the binary data falls within this limit, then it may be possible to embed it directly inside a document.

### Benefits of embedding binary data in MongoDB documents

- All of the benefits listed in the General trade-offs section.
- If binary data that is stored in a document is always used at the same time as the other fields in that document, then all relevant information can be retrieved from the database in a single call, which should provide good performance.
- By embedding binary data in a document, it is guaranteed that the binary data along with the rest of the document is written [atomically](https://docs.mongodb.com/manual/core/write-operations-atomicity/#atomicity-and-transactions).
- It is simple to embed binary data into documents.

### Drawbacks of embedding binary data in MongoDB documents

- All of the drawbacks listed in the General trade-offs section.
- There is a [limit of 16MB per document](https://docs.mongodb.com/manual/reference/limits/#BSON-Document-Size). Embedding large binary objects in documents may risk the documents growing beyond this size limit.
- If the structured metadata in a document is frequently accessed, but the associated embedded binary data is rarely required, then the binary data will be loaded into memory much more often than it is really needed. This is because of the fact that in order to read the structured metadata, the entire document including the embedded binary data is loaded into RAM. This will needlessly waste valuable memory resources and may cause the working set to be pushed out of RAM. This may result in increased disk IO as well as a slower database response time. This drawback can be addressed by separating the binary and associated metadata as I discuss later in this document.

# Considerations for storing binary data in MongoDB with GridFS

If the binary data is bigger than 16MB, then it cannot be stored in a single document. In this case GridFS can be used to get around this limitation.

### Benefits of storing binary data in GridFS

- All of the benefits listed in the General trade-offs section.
- If the binary data is large and/or arbitrary in size, then GridFS may be used to overcome the [16MB limit](https://docs.mongodb.com/manual/reference/limits/#BSON-Document-Size).
- GridFS doesn’t have the limitations of some filesystems, like number of documents per directory, or file naming rules.
- GridFS can be used to recall sections of large files without reading the entire file into memory.
- GridFS can [efficiently stream binary data](https://mongodb.github.io/node-mongodb-native/api-articles/nodekoarticle2.html#advanced-gridfs-or-how-not-to-run-out-of-memory) by loading only a portion of a given binary file into memory at any point in time.

### Drawbacks of storing binary data in GridFS

- All of the drawbacks listed in the General trade-offs section.
- Versus embedding binary data directly into documents, GridFS will have some additional overhead for splitting, tracking, and stitching together the binary data.
- Binary data in GridFS is immutable.

# Considerations for storing binary data outside of MongoDB

In some cases it may be preferable to not store binary data inside MongoDB at all, and instead to store it in an external system.

### Benefits of storing binary data outside of MongoDB

- Storing data outside of MongoDB may reduce storage costs by eliminating MongoDB’s replication of data.
- Binary data outside of MongoDB can be backed up at a different frequency than the database.
- If binary data is stored in a separate system, then binary data will not be loaded into the same RAM as the database. This removes the risk of binary data pushing the working set out of RAM, and ensures that performance will not be negatively impacted.

### Drawbacks of storing binary data outside of MongoDB

- Adding an additional system for the storage of binary data will add significant operational overhead and system complexity versus using MongoDB for this purpose.
- Alternative binary data storage systems will not take advantage of MongoDB’s high availability and replication of data.
- Binary data will not be automatically replicated to geographically distinct data centres.
- Binary data will not be written atomically with respect to its associated document.
- Alternative binary data storage systems will not use MongoDB’s authentication and security mechanisms.

# Mitigating some of the drawbacks of storing binary data in MongoDB

### Separating metadata and embedded binary data into different collections

Instead of embedding binary data and metadata together, it may make sense for binary data to be stored in a collection that is separate from the metadata. This would be useful if metadata is accessed frequently but the associated binary data is infrequently required.

With this approach, instead of embedding the binary data in the metadata collection, the metadata collection would instead contain pointers to the relevant document in a separate binary data collection, and the desired binary data documents would be loaded on-demand. This would allow the documents from the metadata collection to be frequently accessed without wasting memory for the rarely used binary data.

### Separating metadata and binary data into different MongoDB deployments

With this approach as in the previous approach, metadata and binary data are separated into two collections, but additionally these collections are stored on separate MongoDB deployments.

This would allow the binary data deployment to be scaled differently than the metadata deployment. Another benefit of this separation would be that the binary data can be backed up with a different frequency than the metadata.

Note that if metadata is separated into a separate deployment from the associated binary data then special care will have to be taken to ensure the consistency of backups.

# Conclusion

There are several trade-offs to consider when deciding on the best approach for an application to store and retrieve binary data. In this blog post I have discussed several advantages and disadvantages of the most common approaches for storing binary data when working with MongoDB, as well as some techniques for minimising any drawbacks.
