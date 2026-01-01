---
title: "Emulating transactional functionality in Elasticsearch with two-phase commits"
date: 2019-12-05
slug: emulating-transactional-functionality-in-elasticsearch-with-two-phase-commits
aliases:
  - /2019/12/05/emulating-transactional-functionality-in-elasticsearch-with-two-phase-commits/
---

## Introduction

Elasticsearch supports atomic create, update, and delete operations at the individual document level, but does not have built-in [support for multi-document transactions](https://www.elastic.co/blog/found-elasticsearch-as-nosql#transactions). Although Elasticsearch does not position itself as a system of record for storing data, in some cases it may be necessary to modify multiple documents as a single cohesive unit. Therefore, in this blog post we present a [two-phase commit protocol](https://en.wikipedia.org/wiki/Two-phase_commit_protocol) which can be used to _emulate_ multi-document transactions.

## Overview

Create, update, and delete operations in Elasticsearch are atomic at the document level, which means that creating, modifying, or deleting a single document either fully succeeds or fails. However, there is no guarantee that an operation that has multiple steps and that impacts multiple documents will either succeed or fail as a cohesive unit.

In some cases [inner objects and nested types](https://www.elastic.co/blog/managing-relations-inside-elasticsearch) can be used to combine multiple documents into a single atomic unit, which would guarantee atomicity of create, update, and delete operations on the parent and its embedded sub-documents. In other cases it may not be possible or desirable to embed related documents inside a parent document. Therefore multi-document transactional functionality may be desired.

Given the lack of built-in multi-document transactions in Elasticsearch, multi-document transactional functionality that is built on top of Elasticsearch must be implemented in application code. Such functionality can be achieved with the two-phase commit protocol.

## What is the two-phase commit protocol

The [two-phase commit protocol](https://en.wikipedia.org/wiki/Two-phase_commit_protocol) is a type of [atomic commitment protocol](https://en.wikipedia.org/wiki/Atomic_commit) that coordinates processes that participate in a [distributed atomic transaction](https://en.wikipedia.org/wiki/Distributed_transaction). The protocol ultimately determines whether to [commit](https://en.wikipedia.org/wiki/Commit_\(data_management\)) or rollback a transaction. The protocol achieves this goal even in the event of most temporary system failures.

To permit recovery from a failure, the two-phase commit protocol logs the state of a given transaction as the sequential steps to perform the transaction are executed. In the event of a failure at any stage in a transaction these transaction logs will be used by recovery procedures to either complete the transaction or to roll it back.

## A high-level overview of a two-phase commit implementation

In this article, we present an example of a two-phase commit transaction that is used for tracking the movement of “units” between two accounts, as described in the following sections:

1. **Create mappings:** Define the mappings for an accounts index and a transactions index.
2. **Initialize accounts:** Create sample accounts with balances that will be used in subsequent steps to demonstrate how the two-phase commit protocol can be used to ensure completion of the movement of units from one account balance to another.
3. **Define an ingest pipeline for inserting the ingest time:** An ingest pipeline is used to ensure that every transaction has a creation time written into it.
4. **Scripts that are used by the two-phase commit:** Define [painless scripts](https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-scripting-painless.html) which are used in the two-phase commit.
5. **Create a transaction**: A transaction defines which accounts to move units between and how many units to move. It also logs the status of the transaction, which can be used for recovery or rollback.
6. **Core two-phase commit operations**: The steps that will be executed to implement the two-phase commit. By following a specific sequence of operations for multi-document transactions, we maintain sufficient state (i.e. a transaction log) at every step to either fix or rollback transactions that have only partially completed. The core operations are the following:
    1. Update transaction state to “pending”.
    2. Apply the transaction to the source account.
    3. Apply the transaction to the destination account.
    4. Update the transaction state to “committed”.
    5. Remove the transaction identifier from the source account.
    6. Remove the transaction identifier from the destination account.
    7. Update transaction state to “finished”.
7. **Rolling back transactions**: In rare cases some transactions may not be able to complete, and should be rolled-back. This section describes how to undo a two-phase commit that previously started.
8. **Recovering from errors**: This section describes the operations that are periodically executed to detect transactions that have become stuck in one of the two-phase commit or rollback stages. Stalled operation will then be restarted based on the most recent transaction state.

## Create mappings

[Mapping](https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping.html) is the process of defining how a document, and the fields it contains, are stored and indexed. This example defines an accounts index and a transactions index, for which the mappings are defined below.

### Define the mappings for the accounts index

For our example, we define the following fields on the accounts index:

- **balance**: the balance of each account. In this article we refer to the value stored in this field as “units”, which could be a currency, inventory, etc.
- **pending\_transactions**: an array that will contain a list of the \_ids of each transaction that is currently “pending” on each account. The list of pending transactions serves two purposes: (1) it is used for ensuring that the same transaction will never be applied twice to the same account, and (2) it maintains state that will allow rollback steps to set this account back to its pre-transaction state in the event that the transaction cannot run to completion.

Mappings should be defined before writing any documents into the accounts index, as follows:

```
PUT accounts
{
  "mappings": {
    "properties": {
      "balance": {
        "type":  "long"
      }, 
      "pending_transactions": {
        "type": "keyword"
      }
    }
  }
}
```

### Define the mappings for the transactions index

The transactions index will be used for tracking the state of each multi-document transaction, and will have the following fields defined:

- **amount**: the value of the transfer.
- **creation\_time**: when was the transaction created. This is not strictly required, but stored for additional context.
- **modification\_time**: when was the transaction last modified. This will be used for determining if recovery should be started.
- **src\_acct**: the \_id of the source account for the transfer.
- **dest\_acct**: the \_id of the destination account for the transfer.
- **transaction\_state**: one of "created", "pending", "committed", "finished", "terminating", or "rolled-back". In a normal transaction without errors or rollbacks, the transaction state will move from “created” to “pending” to “committed”, and then to “finished”.

Mappings should be defined before writing any documents into the transactions index, as follows:

```
PUT transactions
{
  "mappings": {
    "properties": {
      "amount": {
        "type":  "long"
      },
      "creation_time": {
        "type": "date"
      },
      "modification_time": {
        "type": "date"
      },
      "dest_account": {
        "type": "keyword"
      },
      "src_account": {
        "type": "keyword"
      },
      "transaction_state": {
        "type": "keyword"
      }
    }
  }
}
```

## Initialize accounts

We can initialize documents for accounts A and B, each with a balance of 500 as follows:

```
PUT accounts/_doc/A
{
  "balance": 500,
  "pending_transactions": []
}

PUT accounts/_doc/B
{
 "balance": 500,
 "pending_transactions": []
}
```

## Define an ingest pipeline for inserting the ingest time

The following pipeline will be used to add “creation\_time” and “modification\_time” to the transaction documents. The modification\_time will be required at later stages in the two-phase commit process for detecting transactions that have failed to complete within a reasonable amount of time. The creation time is stored for additional context.

```
PUT _ingest/pipeline/initialize_time
{
 "description": "Add ingest timestamp",
 "processors": [
   {
     "set": {
       "field": "_source.creation_time",
       "value": "{{_ingest.timestamp}}"
     }
   },
   {
     "set": {
       "field": "_source.modification_time",
       "value": "{{_ingest.timestamp}}"
     }
   }
 ]
}

```

## Scripts that are used by the two-phase commit

In this section we define several [painless scripts](https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-scripting-painless.html) which will be executed by update operations that are performed in the two-phase commit steps. Given that updates are atomic, all of the operations inside each of these scripts will either succeed or fail as a unit.

### Script to update the transaction state

This script will be used to update the transaction state from the current state to the desired state. The transaction state can be one of “created”, “pending”, “committed”, “finished”, “terminating”, or “rolled-back”.

Note that if the transaction state on the current transaction is not equal to the current state (e.g. if is already set to the desired state), then this script will not modify the document and the corresponding update operation will return a result of “noop”.

If the transaction state is updated, then this script also updates the modification time of the transaction document which will be required for _Recovering from errors_ procedures.

```
POST _scripts/update_transaction_state
{
  "script": {
    "lang": "painless",
    "source": """
      if (ctx._source.transaction_state == params.current_state) {
        ctx._source.transaction_state = params.desired_state;

        // Set the modification time in ISO 8601 (UTC)
        Date date = new Date();
        DateFormat df = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'");
        df.setTimeZone(TimeZone.getTimeZone("UTC"));
        ctx._source.modification_time = df.format(date);

      } else {
        ctx.op = "noop"
      }
    """
  }
}
```

### Script to apply a transaction to an account

This script is used to add the current transaction amount to an account, and to push the the transaction identifier onto a list of pending transactions. Given the atomic nature of document updates, both of these operations will succeed or fail as an atomic unit. This script will be used for updating accounts once a transaction has entered into the “pending” state.

In the event that the transaction has already been applied to the account (as determined by the transaction identifier being in the array of pending transactions for this account), then this script will not update the document and the corresponding update operation will return a result of “noop”.

```
POST _scripts/apply_transaction_to_account
{
  "script": {
    "lang": "painless",
    "source": """
    
      // Check if the transaction is already stored 
      // in pending_transactions. 
      // If the transaction is already on this account then the 
      // location is >= 0. Otherwise it is -1. 
      def idx = ctx._source.pending_transactions.indexOf(params.trans_id);

      if (idx >= 0) {
        // if the transaction already exists on this account, 
        // do nothing 
        ctx.op = "noop";
      } 
      
      else {
        // New transaction - update the account balance 
        // and add the transaction to pending_transactions
        ctx._source.pending_transactions.add(params.trans_id);
        ctx._source.balance += params.amount;
      }
    """
  }
}
```

### Script to remove a transaction from an account

This script is used for removing a transaction from the pending\_transactions array on an account. This will be done once a transaction is no longer in the “pending” transaction state, and immediately after it has entered into the “committed” transaction state.

In the event that the current transaction has already been removed from the account (as determined by the transaction identifier not appearing in the array of pending transactions for this account), then this script will not modify the document and the corresponding update operation will return a result of “noop”.

```
POST _scripts/remove_transaction_from_account
{
  "script": {
    "lang": "painless",
    "source": """
    
      // Check if the transaction is already stored in 
      // pending_transactions. 
      // If it exists, the location is >= 0. Otherwise is -1. 
      def idx = ctx._source.pending_transactions.indexOf(params.trans_id);
      

      if (idx >= 0) {
        // the transaction exists on this account, remove it 
        ctx._source.pending_transactions.remove(idx);
      } 
      
      else {
        // previously already removed, do nothing 
        ctx.op = "noop";
      }
    """
  }
}
```

### Script to undo a transaction on an account

This script will be used in the event that a transaction is being rolled back. It reverses the previous change that was made to the account balance, and removes the transaction from the account’s pending\_transactions array. Given the atomic nature of document updates, both of these operations will succeed or fail as an atomic unit.

In the event that the current transaction has already been removed from the account (as determined by the transaction identifier not appearing in the array of pending transactions for this account), then this script will not modify the document and the corresponding update operation will return a result of “noop”.

```
POST _scripts/undo_transaction_on_account
{
  "script": {
    "lang": "painless",
    "source": """
    
      // Check if the transaction is already stored in pending_transactions. 
      // If it exists, the location is >= 0. Otherwise is -1. 
      def idx = ctx._source.pending_transactions.indexOf(params.trans_id);
      

      if (idx >= 0) {
        // the transaction exists on this account, remove it 
        ctx._source.pending_transactions.remove(idx);
        ctx._source.balance -= params.amount;
      } 
      
      else {
        // previously already removed, do nothing 
        ctx.op = "noop";
      }
  """
  }
}
```

## Create a transaction

We create a new transaction, and once this transaction has been received by elasticsearch the subsequent steps covered in the remainder of this article will ensure that this transaction will eventually run to completion or will alternatively be rolled-back. This is true even if there is an intermediate failure in any of the individual two-phase commit steps.

Note that the transaction is initially created with a transaction state of “created” and will be moved into a “pending” state when the transaction begins processing. By breaking the transaction into a “created” state followed by a “pending” state, the creation of the  transaction can be decoupled from the two-phase commit processing of the transaction. For example, after receiving confirmation that a transaction has been created, an application can spin up a separate thread to start execution of _Core step 1 - Update transaction state to "pending”,_ and the current thread can immediately respond to the end user with confirmation that the transaction has been received and created. If desired, the application can then periodically poll Elasticsearch to get an updated transaction state which can be displayed to the end user.

We request a transfer of 100 from account A to account B by creating a new document in the transactions index. This request should use the [\_create endpoint](https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-index_.html) with an application-generated transaction identifier (set to “txn1” for this transaction) to ensure idempotency of the transaction creation. This can be done as follows:

```
PUT transactions/_create/txn1?pipeline=initialize_time
{ 
  "src_acct": "A", 
  "dest_acct": "B", 
  "amount" : 100, 
  "transaction_state": "created"
}

```

If we do not receive any response or if it fails, then the above request should be re-submitted, as we are not sure if Elasticsearch received and processed the request for the new transaction. However, because an unacknowledged transaction could theoretically have been received and already changed state due to recovery threads picking it up and moving it forward (this will be covered in detail later in this article), it is important that we are hitting the \_create endpoint, so multiple submissions of a given transaction will not overwrite the transaction state of a transaction that was already accepted.

If the response from Elasticsearch includes “result”: “created”, then the above request has created the document, and we can now begin the two-phase commit of operations for the transaction.

If the application receives a response that indicates “document already exists”, then the transaction document was previously created. In order to avoid the risk of multiple threads simultaneously working on this transaction, do not being two-phase commit operations, and instead let the recovery procedures handle the processing of this transaction.

Note that in subsequent steps we will refer the newly submitted transaction as “curr\_trans”. If the instructions from this blog are being tested in Kibana dev tools, then the values from the above document will need to be manually copied into subsequent commands wherever we refer to “curr\_trans”. If these steps are to be executed in code, then this document could be stored in an object.

## Core two-phase commit operations

In this section we present a two-phase commit which ensures that all steps required to complete a transaction are executed, and that any failed transactions can be detected and executed to completion or alternatively rolled back. This two-phase commit will prevent partial completion of transactions if there is a failure in any of the sequential two-phase commit steps.

Normal two-phase commit operations will execute in a single thread that will start at _Core step 1 - Update transaction state to “pending”,_ and will end at _Core step 7 - Update transaction state to finished._ Recovery procedures may start executing at different stages in the two-phase commit, and will also execute sequentially in a single thread for a single transaction.

If any of the core two-phase commit operations fails or does not receive a response, then it should be retried several times before stopping processing of the current thread. If this happens then the failed transaction will be picked up later by recovery procedures.

### Core step 1 - Update transaction state to "pending"

This step (_Core step 1_) can be arrived at immediately after the transaction has been created, however in the event of an error immediately after creating the transaction, this step will be executed after the step called _Recovery step1 - transactions that are stuck in the “created” state._ The document referred to by “curr\_trans” will be determined by whichever step was executed prior to arriving to this current step.

Update the transaction to indicate that processing has started. This is accomplished by updating the transaction state of the “curr\_trans” document to “pending” as follows:

```
// "txn1" is <curr_trans._id>
POST transactions/_update/txn1?_source
{
  "script": {
    "id": "update_transaction_state",
    "params": {
      "current_state": "created",
      "desired_state": "pending"
    }
  }
}

```

Ensure that the the "result" value in the response is “updated”, and continue to the next step.

If the result field in the response is “noop” then processing of this transaction should be stopped. The \_source returned by the above command should be inspected to ensure that the transaction is in the “pending” state. If necessary, recovery procedures will eventually detect this stopped transaction and then restart the transaction at _Core step 2 - Apply the transaction to the source account_.

If the request fails and continues to fail after several retries, the current thread can exit and the transaction can remain in the “created” state to be detected and fixed by recovery procedures.

### Core step 2 - Apply the transaction to the source account

This step (_Core step 2_) will normally execute immediately after _Core step 1 - Update transaction state to "pending"_. However, in the event of a previous error that has prevented this step from executing, this step may be triggered by the step called _Recover transactions that are in the "pending" transaction state_.

Update the balance and pending\_transactions in the source account in the source account as follows:

```
// "A" is from <curr_trans._source.src_acct>
POST accounts/_update/A?_source
{
  "script": {
    "id": "apply_transaction_to_account",
    "params": {
      "trans_id": "txn1", // from <curr_trans._id>
      "amount": -100      // i.e. remove <curr_trans._source.amount>
    }
  }
}
```

The response to the above command should normally have a result of “updated”.

If it returns a result of “noop”, then the returned \_source should be inspected to ensure that the transaction has already been applied to the source account. As long as the transaction has been applied to the source account, continue to the next step as we must guarantee that the destination account is also updated before continuing on to change the transaction state to “committed”.

If the request fails and continues to fail after several retries, do not continue to the next step, as the transaction should remain in the “pending” state to be detected and fixed by recovery procedures.

### Core step 3 - Apply the transaction to the destination account

This step (_Core step 3_) will execute immediately after _Core step 2._ Execute the following code to apply the transaction to the destination account:

```
// "B" is from <curr_trans._source.dest_acct>
POST accounts/_update/B?_source
{
  "script": {
    "id": "apply_transaction_to_account",
    "params": {
      "trans_id": "txn1", // from <curr_trans._id>
      "amount": 100       // from +<curr_trans._source.amount>
    }
  }
}
```

The response to the above command should return a result with the value “updated”.

If it returns a result of “noop”, then the returned \_source should be inspected to ensure that the transaction has already been applied to the destination account. As long as the transaction has been applied to the destination account, continue with the next step to update the transaction state to “committed”.

If the request fails and continues to fail after several retries, do not continue to the next step, as the transaction should remain in the “pending” state to be detected and fixed by recovery procedures.

### Core step 4 - Update the transaction state to "committed"

This step (_Core step 4_) will only be called immediately after a pending transaction has been applied to both the source account and the destination account. This step is not called directly by any recovery procedures. This ensures that a “committed” transaction state means that both the source and destination balances are guaranteed to have have been updated.

Once a transaction moves into a “committed” transaction state, the order of execution of the two-phase commit steps (or of the recovery procedures) guarantee that no further attempts to modify the source or destination account balances will take place for the current transaction.

Execute the following command to update the transaction state to “committed”:

```
// "txn1" is <curr_trans._id>
POST transactions/_update/txn1?_source
{
  "script": {
    "id": "update_transaction_state",
    "params": {
      "current_state": "pending",
      "desired_state": "committed"
    }
  }
}

```

Ensure that the the "result" value in the response is equal to “updated”, and continue to the next step.

If the result field in the response is “noop” then processing of this transaction should be stopped. The returned \_source should be inspected to ensure that the transaction is in the “committed” state. If necessary, recovery procedures will eventually detect this stopped transaction and will then restart the transaction at _Core step 5 - Remove the transaction from the source account_.

If the request fails and continues to fail after several retries, the current thread can exit as the transaction can remain in the “pending” state to be detected and fixed by recovery procedures.

### Core step 5 - Remove the transaction identifier from the source account

This step (_Core step 5_) will normally execute immediately after _Core step 4 - Update transaction state to "committed"_. However, in the event of a previous error that has prevented this step from executing, this will be called after _Recover transactions that are in the "committed" transaction state_.

The transaction id in the pending transactions array on the source account was previously required to ensure that a given transaction would only be applied once to the source account’s balance. Now that the account balances have been committed, this can now be removed as follows:

```
// "A" is from <curr_trans._source.src_acct>
POST accounts/_update/A?_source
{
  "script": {
    "id": "remove_transaction_from_account",
    "params": {
      "trans_id": "txn1" // from <curr_trans._id>
    }
  }
}

```

The response to the above command should normally have a result of “updated”.

If it returns a result of “noop”, the returned \_source should be inspected to ensure that the transaction has been removed from the source account. If so, continue to the next step as we must guarantee that the destination account is also updated before moving to the “finished” state.

If the request fails and continues to fail after several retries, do not continue to the next step, as the transaction should remain in the “committed” state to be detected and fixed by future recovery procedures.

### Core step 6 - Remove the transaction identifier from the destination account

This step (_Core step 6_) will execute immediately after _Core step 5._ We can remove the transaction from the destination account as follows:

```
// "B" is from <curr_trans._source.dest_acct>
POST accounts/_update/B?_source
{
  "script": {
    "id": "remove_transaction_from_account",
    "params": {
      "trans_id": "txn1" // from <curr_trans._id>
    }
  }
}
```

The response to the above command should return a result with the value “updated”.

If it returns a result of “noop”, the returned \_source should be inspected to ensure that the transaction has been removed from the destination account. If so, continue to the next step.

If the request fails and continues to fail after several retries, do not continue to the next step, as the transaction should remain in the “committed” state to be detected and fixed by recovery procedures.

### Core step 7 - Update transaction state to "finished"

This step (_Core step 7_) will only be called immediately after a committed transaction has been removed from both the source account and the destination account. This step is not called directly by any recovery procedures. This sequence ensures that a “finished” transaction state means that the current transaction has been removed from both the source and destination account’s pending transactions arrays.

Execute the following command to update the transaction state to “finished”:

```
// "txn1" is <curr_trans._id>
POST transactions/_update/txn1?_source
{
  "script": {
    "id": "update_transaction_state",
    "params": {
      "current_state": "committed",
      "desired_state": "finished"
    }
  }
}

```

The response to the above command should normally return a result with the value “updated”.

If it returns a result of “noop”, then inspect the returned \_source to confirm that the transaction state is “finished”.

If the request fails and continues to fail after several retries, the current thread can exit as the transaction can remain in the “committed” state to be detected and fixed by recovery procedures.

## Rolling back transactions

In some cases it may be necessary to roll back a transaction, which can be done as described below.

### Rollback of “created” transactions

A transaction that is in a “created” state can be directly set to “rolled-back”. This can be accomplished as follows:

```
// "txn1" is <curr_trans._id>
POST transactions/_update/txn1?_source
{
  "script": {
    "id": "update_transaction_state",
    "params": {
      "current_state": "created",
      "desired_state": "rolled-back"
    }
  }
}

```

If the result field in the response is “updated” then rollback of this transaction has succeeded.

If the result is “noop” then the transaction may have already moved past the “created” state, and therefore an alternate rollback procedure should be followed, depending on the current state of the transaction. The current transaction state can be viewed in the returned \_source.

### Rollback of “pending” transactions

If a transaction is in the "pending" state, then the transaction can be rolled-back by executing the following steps which will reverse the modifications to the source and destination accounts, as well as change the status of the transaction..

#### Rollback step 1 - Update the transaction state to "terminating"

Update the transaction state on the current transaction from “pending” to “terminating” as shown below.

```
// "txn1" is <curr_trans._id>
POST transactions/_update/txn1?_source
{
  "script": {
    "id": "update_transaction_state",
    "params": {
      "current_state": "pending",
      "desired_state": "terminating"
    }
  }
}

```

The response to the above command should return a result with the value “updated”.

If a result of “noop” is returned in the response, then the rollback of the current transaction should be stopped and the returned \_source should be inspected to confirm that the transaction is not in the “pending” state, and that it is already in either the “committed” state or “terminating” state.

If the request fails and continues to fail even after several retries, the current thread should exit as the transaction should remain in the “pending” state to be detected and fixed by normal _Recovering from errors in the two-phase commit_ procedures (which, if successful, would move the transaction to a “finished” state, rather than “rolled-back), or alternatively a new rollback can be retried.

#### Rollback step 2 - Undo the transaction on the source account

This step (_Rollback step 2_) can be arrived at immediately after the transaction has been set to the “terminating” state, however in the event of an error after updating the state, this step will be executed after the step called _Recover transactions that are in the "terminating" transaction state_.

If the source account balance has been modified, then it will have an entry for the current transaction’s \_id in its pending transactions array. Therefore the amount that was removed from the source account balance must be added back, and the transaction must be removed from the pending transactions array. This can be accomplished with the following code:

```
// "A" is from <curr_trans._source.src_acct>
POST accounts/_update/A?_source
{
  "script": {
    "id": "undo_transaction_on_account",
    "params": {
      "trans_id": "txn1", // <curr_trans._id>
      "amount": -100      // Undo -<curr_trans._source.amount>
    }
  }
}

```

The response to the above command should normally have a result of “updated”.

If it returns a result of “noop”, the returned \_source should be inspected to confirm that the transaction has already been rolled-back on the source account. In this case, continue to the next step as it is possible that the destination account has not yet been rolled-back.

If the request fails and continues to fail even after several retries, the current thread should exit as the transaction should remain in the “terminating” state to be detected and fixed by recovery procedures.

#### Rollback step 3 - Undo the transaction from the destination account

If the destination account balance has been modified, then it will have an entry for the current transaction’s \_id in its pending transactions array. Therefore the amount that was added to the destination account balance must be removed, and the transaction must be removed from the pending transactions array. This can be accomplished with the following code:

```
// "B" is from <curr_trans._source.dest_acct>
POST accounts/_update/B?_source
{
  "script": {
    "id": "undo_transaction_on_account",
    "params": {
      "trans_id": "txn1", // <curr_trans._id>
      "amount": 100      //  Undo <curr_trans._source.amount>
    }
  }
}

```

The response to the above command should normally have a result of “updated”.

If it returns a result of “noop”, the returned \_source should be inspected to confirm that the transaction has already been rolled-back on the destination account. In this case, continue to the next step as the transaction state needs to be set to “rolled-back”.

If the request fails and continues to fail even after several retries, the current thread should exit as the transaction should remain in the “terminating” state to be detected and fixed by recovery procedures.

#### Rollback step 4 - Set the transaction state to “rolled-back”

The rollback operation is completed by updating the transaction state to “rolled-back”.

```
// "txn1" is <curr_trans._id>
POST transactions/_update/txn1?_source
{
  "script": {
    "id": "update_transaction_state",
    "params": {
      "current_state": "terminating",
      "desired_state": "rolled-back"
    }
  }
}

```

The response to the above command should return a result with the value “updated”.

If the response result is “noop”, then the returned \_source should be inspected to confirm that the transaction state has already been set to “rolled-back”.

If the request fails and continues to fail even after several retries, the current thread should exit as the transaction should remain in the “terminating” state, which will be detected and fixed by recovery procedures.

### Rollback of “committed” transactions

If a transaction is in the "committed" state, then it should be allowed to complete (i.e. it should be allowed to move to a transaction state of “finished”). After completion, then another transaction can be executed to reverse the transaction.

If for some reason a transaction in the “committed” state cannot proceed to the “finished” state on its own, even after the steps in _Recover transactions that are in the "committed" transaction state_ have been executed, then manual intervention may be required to understand and fix the root cause of the issue.

## Recovering from errors

Recovery operations can be looped over to detect and recover from a failure in any of the stages in the _Core two-phase commit operations_. Recovery should only be initiated on a transaction that has not completed within a _reasonable_ amount of time since its last update (i.e. since its modification timestamp). Recovery should not be attempted on transactions that may still be executing, or that may have unacknowledged modifications to their transaction state, as this could introduce race conditions.

A simple heuristic to ensure that recovery is not attempted on transactions that are currently executing is the following:

1. Before recovering a transaction, wait until the time that has passed since its last modification is greater than the maximum processing time of all two-phase commit steps. In other words, wait long enough to ensure that the transaction should have either executed to completion or failed, including retries and timeouts.
2. Ensure that the looping of the recovery operation does not happen faster than the maximum processing time of all two-phase commit steps. In other words, do not start the next iteration of the recovery loop until after waiting long enough to ensure that previous recovery operations will have either completed or failed, including retries and timeouts.

Unacknowledged modifications (a.k.a. [dirty reads](https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-replication.html)) can be avoided by using the modification\_time to compute how much time has passed since the last update to the transaction, and not attempting to recover a transaction until several minutes have passed since its most recent update. This will give elastic sufficient time to detect and fix any unacknowledged writes.

In the examples below, we wait 2 minutes from the most recent update to a transaction before we attempt recovery, which should meet the above requirements. We could also consider executing the recovery loop once every minute. Both of these values should be validated based on the timeouts and number of retries for a given implementation.

More sophisticated and precise control over the timing of the launching of recovery procedures could be achieved by maintaining a mapping of transactions and their associated threads. Before launching a recovery procedure, the thread associated with each transaction could be checked to ensure that it is no longer alive. The details of such an implementation will be language dependent, and are beyond the scope of this article.

### Get transactions that need to be recovered

Transactions that have not been modified in the past 2 minutes, may be “stuck”, and can be detected with the following query:

```
GET transactions/_search
{
 "size": 100,
 "query": {
   "bool": {
     "filter": [
       {
         "terms": {
           "transaction_state": [
             "created", 
             "pending",
             "terminating", 
             "committed"
             ]
         }
       },
       {
         "range": {
           "modification_time": {
             "lte": "now-2m"
           }
         }
       }

     ]
   }
 },
 "sort": [
   {
     "modification_time": {
       "order": "asc"
     }
   }
 ]
}
```

### Recover transactions that are stuck in the “created” state

For each “created” transaction returned from the above query, create a new thread to resume executing it starting at _Core step 1 - Update transaction state to "pending"_.

### Recover transactions that are in the "pending" state

For each “pending” transaction returned from the above query, create a new thread to resume executing it starting at Core step 2 _- Apply the transaction to the source account_.

### Recover transactions that are in the "committed" state

For each “committed” transaction that is returned, create a new thread to resume executing it starting at _Core step 5 - Remove the transaction from the source account_.

### Recover transactions that are in the "terminating" state

For each “pending” transaction that is returned, create a new thread to resume executing it starting at _Rollback step 2 - Undo the transaction on the source account_.

### Recover very long running transactions

If any “created”, “pending”, or “committed” transactions are returned that have a modification time that is more than an hour ago, they may need additional investigations and should possibly be rolled back as described in the _Rolling back transactions_ section.

If a “terminating” transaction is unable to move into the “rolled-back” transaction state, then it should be investigated and manual intervention may be required.

## Conclusions

In some cases it may be necessary to modify multiple documents as a single cohesive unit. Elasticsearch does not have built-in [support for multi-document transactions](https://www.elastic.co/blog/found-elasticsearch-as-nosql#transactions), therefore in this blog this blog post we have presented a [two-phase commit protocol](https://en.wikipedia.org/wiki/Two-phase_commit_protocol) which can be used to _emulate_ multi-document transactions.
