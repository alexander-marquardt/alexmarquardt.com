---
title: "Case-insensitive character filter in Elasticsearch"
draft: true
---

# Background

When ingesting code into Elasticsearch, you may have certain words that should not be split up. For example, the word "X-Pack" should likely be stored as a single token. However, due to the way that most [analyzers](https://www.elastic.co/guide/en/elasticsearch/reference/7.8/analyzer-anatomy.html) work, this "word" would be tokenized into two words: "X" and "Pack".

Because an analyzer consists of [character filters](https://www.elastic.co/guide/en/elasticsearch/reference/7.8/analyzer-anatomy.html#analyzer-anatomy-character-filters), followed by a [tokenizer](https://www.elastic.co/guide/en/elasticsearch/reference/7.8/analyzer-anatomy.html#analyzer-anatomy-tokenizer), followed by [token filters](https://www.elastic.co/guide/en/elasticsearch/reference/7.8/analyzer-anatomy.html#analyzer-anatomy-token-filters), if we want to prevent a word such as X-Pack from being split apart into multiple tokens, we can design a custom character filter to modify the word _before_ it gets to the tokenizer.

For example,

Therefore, one can create a custom analyzer similar to the following which would make use of a custom character filter to convert

 

Show example, using the above.

 

 

 

https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-charfilters.html

 

 

```
PUT blogs_test
{
  "settings": {
    "analysis": {
      "char_filter": {
        "my_lowercase_char_filter": {
          "type": "pattern_replace",
          "pattern": "(?i)(X-Pack)",
          "replacement": "xpack"
        }
      },
      "analyzer": {
        "my_content_analyzer": {
          "type": "custom",
          "char_filter": [
            "my_lowercase_char_filter"
          ],
          "tokenizer": "standard",
          "filter": [
            "lowercase"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "my_content_analyzer"
      }
    }
  }
}

POST blogs_test/_analyze
{
  "text": ["We love x-Pack"],
  "analyzer": "my_content_analyzer"
}
```
