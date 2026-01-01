---
showtoc: true
title: "How to manually perform a point in time restore in MongoDB"
date: 2017-01-25
slug: mongodb-point-in-time-restore
aliases:
  - /2017/01/25/mongodb-point-in-time-restore/
---

### ![human-error-in-finance](images/human-error-in-finance.jpg)

## Introduction

While MongoDB provides high-availability and data durability through [automatic replication](https://docs.mongodb.com/manual/replication/) of data to multiple servers, this replication does not protect the database against human or application errors. For example, if an administrator drops a database, the drop operation will be replicated across the MongoDB deployment, and data will be deleted. If such an event occurs through human or application error, then data will have to be retrieved from backups.

## Recommended background

It is recommended that you review and understand the standard [MongoDB Backup Methods](https://docs.mongodb.com/manual/core/backups/) before attempting a manual point-in-time backup and restore.

## Purpose

In this blog, we describe a procedure that allows you to manually perform a point-in-time restore of MongoDB data. Point-in-time restore refers to the ability to restore the database to a precise moment in time. The instructions presented here require that you have regular backups of your data, and that your data is stored in a replica set.

**\*\*\* WARNING \*\*\* :** This manual point-in-time backup and restore procedure should not be used on sharded clusters.   

## Alternatives to manual point-in-time restores

While the purpose of this blog is to demonstrate a manual point-in-time restore procedure, the reader should be aware that MongoDB has software available that automates backups and provides point-in-time restores, and that is designed to work with  any kind of database configuration, including sharded clusters.

For more information about MongoDB's recommended solutions, read about [Ops Manager](https://www.mongodb.com/products/ops-manager), [Cloud Manager](https://www.mongodb.com/cloud/cloud-manager), and  [Atlas](https://www.mongodb.com/cloud/atlas).

Note that these recommended solutions will likely not be not help you automate the point-in-time restore procedure unless the same tool was used for creating the original backups.

## Requirements

In order to perform a manual point-in-time restore, you need two things:

1. You need a backup of the database - this can be either from a mongodump or from a file system copy.
2. You need access to an [oplog](https://docs.mongodb.com/manual/core/replica-set-oplog/) that contains data that goes back to when the backup was made. For example if you made a backup 24 hours ago, then you need an oplog that goes back at least 24 hours. This oplog will be extracted from one of the replica set members in the live database.

## How does it work

A manual point-in-time restore is achieved by copying a database backup to a spare server and starting the database on that spare server with the backup data. We then "roll forward" the data on the spare server to the desired point-in-time, which is achieved by dumping the oplog from the live/production database, copying the oplog over to the spare server, and then applying the oplog onto the database that we are now running on the spare server.

After we have verified that the restored data is correct, we then copy it from our spare server over to our production servers.

## **Example scenario**

A concrete example of how a point-in-time restore can be performed is as follows. For this example we assume the following.

1. You have a backup mongodump or snapshot of the database from 24 hours ago
2. You have the oplog on your live/production database that goes back at least 24 hours (ie. an oplog window of at least 24 hours). The oplog is available on each node in the replica set, and can be dumped out from any one of the replica set members. The oplog contains a record of all database events that have recently occurred. 
3. You realize that one hour ago, someone did something really bad (eg. dropped a collection or dropped a database)

For this scenario, the following steps will result in a point-in-time restore:

1. Restore or copy the backup from 24 hours ago onto a spare server.  This server will be used for recreating the database state as it was just before the data loss occurred.
2. Dump out the oplog from the live/production replica set where the error occurred. The oplog contains a log of every operation that has recently occurred on the live/production database.
3. Copy the oplog over to the spare server.
4. Replay 23 hours of the oplog onto the backup to "roll it forward" to just before the undesirable incident that happened (in this example, one hour ago). 
5. Verify the database on the spare server, and if it looks good, copy it over to the production servers.

## **Restoration instructions:**

1. On one of the members of your live replica set, dump the oplog collection using mongodump:
    
    ```
    mongodump ­-d local -c oplog.rs ­-o oplogDumpDir/
    ```
    
2. Rename and move the dump of the oplog from the live deployment:
    
    ```
    mkdir oplogRecoveryDir
    mv oplogDumpDir/local/oplog.rs.bson oplogRecoveryDir/oplog.bson
    
    ```
    
3. Connect to the server using the mongo shell, find the bad operation in the oplog and make a note of the **time\_t:ordinal** (timestamp) values. Alternatively, use bsondump to manually inspect the BSON dump of the oplog.
    
    ```
    mongo
    use local
    db.oplog.rs.find(...)
    ```
    
4. Start a new standalone mongod instance to rebuild the server and verify the data before applying it to production. If you use mongorestore to restore a backup, then use step **a**, and if you are restoring from a data file backup see step **b**:
    - (a) Start a new mongod process, and restore the last known good backup using mongorestore. For this example the data is located in a directory called "backupDumpDir". Note that if the original mongodump was done on a database that was being actively written during the dump, then it should have been made with the --oplog option. In this case, the mongorestore should be done with the --oplogReplay option to ensure that the backup data is restored in a consistent state.
        
        ```
        mongod --­­dbpath /some/new/directory --­­port PORT
        mongorestore --port PORT [--oplogReplay] backup­DumpDir/
        ```
        
    - (b) Or if you have a file system backup, then you can copy the data from your backup to the dbpath directory, and start mongod directly as follows:
        
        ```
        mongod --­­dbpath /path/to/backupDataDir --­­port PORT
        ```
        
5. Replay the oplog into the new node using mongorestore, specifying the values for **time\_t** and **ordinal** as found above. This command will replay the oplog up to the point just before the bad operation occurred. 
    
    ```
    mongorestore --­­port --­­oplogReplay --­­oplogLimit time_t:ordinal oplogRecoveryDir/
    ```
    
6. Check that all documents are now back in the collection and data has been correctly restored. If this is successful take a server dump by either of the following steps.
    - (a) Using mongodump:
        
        ```
        mongodump ­­--port PORT rebuildDumpDir/
        ```
        
    - (b) Or by taking a file system snapshot (eg. LVM Snapshot), or by stopping writes to the mongod process and copying the database data files.
7. Depending on the procedure used in the previous steps, restore the dump or the data files into the live/production replica set by either:
    - (a) Using the standard mongorestore procedure as documented in [Backup and Restore with MongoDB Tools](https://docs.mongodb.com/manual/tutorial/backup-and-restore-tools/).
    - (b) Or by copying the appropriate data files as documented in [Restore a Replica Set from MongoDB Backups](https://docs.mongodb.com/manual/tutorial/restore-replica-set-from-backup/).

## Related issues

If you encounter issues restoring data with the above procedure, you should view the following MongoDB Jira tickets to see if they are related:

- [https://jira.mongodb.org/browse/TOOLS-176](https://jira.mongodb.org/browse/TOOLS-176)
- [https://jira.mongodb.org/browse/SERVER-10773](https://jira.mongodb.org/browse/SERVER-10773)
- [https://jira.mongodb.org/browse/SERVER-12508](https://jira.mongodb.org/browse/SERVER-12508)
- [https://jira.mongodb.org/browse/SERVER-19618](https://jira.mongodb.org/browse/SERVER-19618)
