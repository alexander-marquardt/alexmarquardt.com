---
title: ""
date: 2025-12-30
---

# About this site

This site collects my technical writing on search, data pipelines, and distributed systems. Topics include relevance, performance, reliability, data ingestion, and maintainable system architecture.

# Professional context

I am a Senior Principal Architect working on GenAI and Search at [Elastic](https://www.elastic.co/). Earlier work in FPGA architecture and placement & routing algorithms produced peer-reviewed publications that have been cited over [3,600 times](https://scholar.google.co.uk/citations?user=d-dosjEAAAAJ&hl=en).

Details on publications, patents, and open-source contributions are in my [Professional record](/professional/). Additional background is available on [LinkedIn](https://www.linkedin.com/in/alexandermarquardt/).

## Search & Relevance

- [Influencing BM25 ranking with multiplicative boosting in Elasticsearch | Elasticsearch Labs](https://www.elastic.co/search-labs/blog/bm25-ranking-multiplicative-boosting-elasticsearch) (Dec 22, 2025)

- [Boosting e-commerce search by profit and popularity with the function score query in Elasticsearch | Elasticsearch Labs](https://www.elastic.co/search-labs/blog/function-score-query-boosting-profit-popularity-elasticsearch) (Dec 17, 2025)

- [How to improve e-commerce search relevance with personalized cohort-aware ranking | Elasticsearch Labs](https://www.elastic.co/search-labs/blog/ecommerce-search-relevance-cohort-aware-ranking-elasticsearch) (Dec 10, 2025)

- [Personalizing e-commerce search results based on purchase history in Elasticsearch](/elastic/personalizing-search-in-elasticsearch-without-ml-post-processing/) (Sep 12, 2025)

- [Efficient bitwise matching of documents in Elasticsearch | Elasticsearch Labs](https://www.elastic.co/search-labs/blog/efficient-bitwise-matching-in-elasticsearch) (Oct 21, 2024)

- [Improve search relevance by combining Elasticsearch stemmers and synonyms | Elastic Blog](https://www.elastic.co/blog/improve-search-relevance-by-combining-elasticsearch-stemmers-and-synonyms) (June 23, 2021)

- [Improving search relevance with boolean queries | Elastic Blog](https://www.elastic.co/blog/how-to-improve-elasticsearch-search-relevance-with-boolean-queries) (May 26, 2020)

## Performance, Reliability & Failure Analysis

- [How excessive replica counts can degrade performance, and what to do about it | Elasticsearch Labs](https://www.elastic.co/search-labs/blog/elasticsearch-replica-counts-right-sizing) (Dec 8, 2025)

- [Understanding and fixing "too many script compilations" errors in Elasticsearch](/elastic/elasticsearch-too-many-script-compilations/) (Oct 21, 2020)

- [Using slow logs in Elastic Cloud Enterprise](/elastic/using-slow-logs-in-elastic-cloud-enterprise/) (Apr 26, 2020)

- [Using parallel Logstash pipelines to improve persistent queue throughput | Elastic Blog](https://www.elastic.co/blog/using-parallel-logstash-pipelines-to-improve-persistent-queue-performance) (Nov 14, 2019)

- [Improving the performance of high-cardinality terms aggregations | Elastic Blog](https://www.elastic.co/blog/improving-the-performance-of-high-cardinality-terms-aggregations-in-elasticsearch) (May 9, 2019)

- [How to tune Elasticsearch for aggregation performance](/elastic/how-to-tune-elasticsearch-for-aggregation-performance/) (Oct 2, 2018)

## Ingest Architecture

- [Re-directing Elasticsearch documents with out-of-range timestamps that (would) fail to get written into Time Series Data Streams](/elastic/catching-elasticsearch-documents-with-incorrect-timestamps-that-fail-to-get-written-into-time-series-data-streams/) (Apr 16, 2024)

- [Driving Filebeat data into separate indices (uses legacy index templates)](/elastic/driving-filebeat-data-into-separate-indices-uses-legacy-index-templates/) (March 15, 2021)

- [How to create maintainable and reusable Logstash pipelines | Elastic Blog](https://www.elastic.co/blog/how-to-create-maintainable-and-reusable-logstash-pipelines) (Feb 27, 2020)

- [Using Logstash to Split Data and Send it to Multiple Outputs | Elastic Blog](https://www.elastic.co/blog/using-logstash-to-split-data-and-send-it-to-multiple-outputs) (Jan 15, 2019)

## Data Parsing & Structuring

- [Using Kibana’s Painless Lab (Beta) to test an ingest processor script](/elastic/using-kibanas-painless-lab-beta-to-test-an-ingest-processor-script/) (Nov 9, 2020)

- [Using Elasticsearch Painless scripting to recursively iterate through JSON fields](/elastic/using-elasticsearch-painless-scripting-to-iterate-through-fields/) (Nov 6, 2020)

- [Debugging broken grok expressions in Elasticsearch ingest processors | Elastic Blog](https://www.elastic.co/blog/debugging-broken-grok-expressions-in-elasticsearch-ingest-processors) (Sep 3, 2020)

- [Slow and steady: How to build custom grok patterns incrementally | Elastic Blog](https://www.elastic.co/blog/slow-and-steady-how-to-build-custom-grok-patterns-incrementally) (Aug 26, 2020)

- [Structuring Elasticsearch data with grok on ingest for faster analytics | Elastic Blog](https://www.elastic.co/blog/structuring-elasticsearch-data-with-grok-on-ingest-for-faster-analytics) (Jul 30, 2020)

- [Converting CSV to JSON in Filebeat](/elastic/converting-csv-to-json-in-filebeat/) (Mar 17, 2020)

- [Using Logstash prune capabilities to whitelist sub-documents](/elastic/using-logstash-prune-capabilities-to-whitelist-sub-documents/) (Aug 28, 2018)

## Data Derivation & Enrichment

- [Using Logstash to scan inside event contents and to replace sensitive data with a consistent hash](/elastic/using-logstash-to-hash-sensitive-text/) (Jan 20, 2022)

- [Using Logstash and Elasticsearch to calculate transaction duration in a microservices architecture](/elastic/using-logstash-and-elasticsearch-scripted-upserts-to-calculate-transaction-duration-from-out-of-order-events/) (Sep 16, 2020)

- [How to enrich logs and metrics using an Elasticsearch ingest node | Elastic Blog](https://www.elastic.co/blog/how-to-enrich-logs-and-metrics-using-an-elasticsearch-ingest-node) (May 12, 2020)

- [Enriching data with the Logstash translate filter](/elastic/enriching-data-with-the-logstash-translate-filter/) (Mar 6, 2020)

- [Using Logstash and Elasticsearch scripted upserts to transform eCommerce purchasing data](/elastic/logstash-and-elasticsearch-painless-scripted-upserts-transform-data/) (Dec 17, 2019)

## End-to-End Systems & Reference Implementations

- [ES Local Indexer – Desktop search powered by Elasticsearch](/elastic/es-local-indexer-desktop-search-built-with-elasticsearch/) (Aug 7, 2019)

- [How to keep Elasticsearch synchronized with a relational database using Logstash | Elastic Blog](https://www.elastic.co/blog/how-to-keep-elasticsearch-synchronized-with-a-relational-database-using-logstash) (Jun 20, 2019)

## Operational Foundations

- [Safely sample production data into pre-production environments with Logstash | Elastic Blog](https://www.elastic.co/blog/production-data-pre-production-environments-logstash) (Oct 1, 2024)

- [Automating the Import and Export of Kibana Saved Objects](/elastic/automating-the-import-and-export-of-kibana-saved-objects/) (May 3, 2024)

- [Calculating ingest lag and storing ingest time in Elasticsearch to improve observability | Elastic Blog](https://www.elastic.co/blog/calculating-ingest-lag-and-storing-ingest-time-in-elasticsearch-to-improve-observability) (Jun 16, 2020)

- [Converting local time to ISO 8601 time in Elasticsearch | Elastic Blog](https://www.elastic.co/blog/converting-local-time-to-iso-8601-time-in-elasticsearch) (Nov 7, 2019)

- [Counting unique beats agents sending data into Elasticsearch](/elastic/counting-unique-beats-agents-elasticsearch/) (Jul 18, 2019)

## Correctness, Consistency & Security

- [Emulating transactional functionality in Elasticsearch with two-phase commits](/elastic/emulating-transactional-functionality-in-elasticsearch-with-two-phase-commits/) (Dec 5, 2019)

- [Elasticsearch Security: Configure TLS/SSL & PKI Authentication | Elastic Blog](https://www.elastic.co/blog/elasticsearch-security-configure-tls-ssl-pki-authentication) (Dec 12, 2018)

- [How to Find and Remove Duplicate Documents in Elasticsearch | Elastic Blog](https://www.elastic.co/blog/how-to-find-and-remove-duplicate-documents-in-elasticsearch) (Dec 11, 2018)

## System Behavior & Advanced Techniques

- [Using Elastic machine learning to detect anomalies in derivative values](/elastic/using-elastic-machine-learning-to-detect-anomalies-in-derivative-values/) (Apr 21, 2020)

- [How to Debug Elasticsearch Source Code in IntelliJ IDEA | Elastic Blog](https://www.elastic.co/blog/how-to-debug-elasticsearch-source-code-in-intellij-idea) (Feb 14, 2019)

# Airbyte

- [Using the new Airbyte API to orchestrate Airbyte Cloud with Airflow](https://airbyte.com/blog/orchestrating-airbyte-api-airbyte-cloud-airflow) (Mar 2, 2023)

- [The difference between Airbyte and Airflow](https://airbyte.com/blog/airbyte-vs-airflow) (Feb 24, 2023)

- [Learn how to create an Airflow DAG (directed acyclic graph) that triggers Airbyte synchronizations](https://airbyte.com/tutorials/how-to-use-airflow-and-airbyte-together) (Feb 8, 2023)

- [You have collected unstructured data! Now what?](https://airbyte.com/blog/analyze-unstructured-data) (Jan 11, 2022)

- [Data Warehouse vs. Operational Database! What? How? Which One?](https://airbyte.com/blog/data-warehouse-vs-operational-database) (Dec 16, 2022)

- [What is an ELT data pipeline?](https://airbyte.com/blog/elt-pipeline) (Nov 17, 2022)

- [EtLT for improved GDPR compliance](https://airbyte.com/blog/etlt-gdpr-compliance) (Oct 20, 2022)

- [An overview of Airbyte’s replication modes](https://airbyte.com/blog/understanding-data-replication-modes) (Oct 7, 2022)

- [Explore Airbyte's Change Data Capture (CDC) synchronization](https://airbyte.com/tutorials/incremental-change-data-capture-cdc-replication) (Sep 29, 2022)

- [Explore Airbyte’s incremental data synchronization](https://airbyte.com/tutorials/incremental-data-synchronization) (Sep 8, 2022)

- [Explore Airbyte's full refresh data synchronization](https://airbyte.com/tutorials/full-data-synchronization) (Aug 2, 2022)

- [Build a connector to extract data from the Webflow API](https://airbyte.com/tutorials/extract-data-from-the-webflow-api) (June 29, 2022)

- [Data Integration Guide: Techniques, Technologies, and Tools](https://airbyte.com/blog/data-integration) (May 19, 2022)

# MongoDB

- [Trade-offs to consider when storing binary data in MongoDB](/mongodb/trade-offs-to-consider-when-storing-binary-data-in-mongodb/) (Mar 2, 2017)

- [How to generate unique identifiers for use with MongoDB](/mongodb/how-to-generate-unique-identifiers-for-use-with-mongodb/) (Jan 30, 2017)

- [How to manually perform a point in time restore in MongoDB](/mongodb/mongodb-point-in-time-restore/) (Jan 25, 2017)

# Additional Information

- [About the Author](/about/)
- [Professional Record](/professional/)
- [Other Areas of Interest](/personal/)
