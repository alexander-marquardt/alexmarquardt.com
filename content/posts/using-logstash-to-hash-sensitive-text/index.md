---
title: "Using Logstash to scan inside event contents to replace sensitive data with a consistent hash"
date: 2022-01-20
---

## Introduction

[Logstash](https://www.elastic.co/logstash/) is commonly used for transforming data before it is sent to another system for storage, and so it is often well positioned for finding and replacing sensitive text, as may be required for GDPR compliance.

Therefore, in this blog I show how Logstash can make use of a ruby filter to scan through the contents of an event and to replace _each occurrence_ of sensitive text with the value of its hash.

This is done by making use of Ruby's [gsub](https://ruby-doc.org/core-2.4.2/String.html#method-i-gsub) functionality, providing a definition of a regular expression pattern that will be replaced (in this blog, we demonstrate with an email address regex pattern), and by executing a hash function to calculate the replacement value.

Note that the use case addressed in this blog is different than the use cases for the [fingerprint filter](https://www.elastic.co/guide/en/logstash/current/plugins-filters-fingerprint.html). The fingerprint filter can combine and hash one or more fields, but it does not analyze or replace substrings inside the field(s).

This blog also demonstrates several other Logstash concepts, including:

1. Use of a generator in Logstash to automatically create new events to make testing of your filters quick and easy.
2. Defining custom ruby code inside your Logstash pipeline.
3. Use of the stdout output to easily debug your Logstash pipeline.
4. Automatic reload functionality to allow you to immediately validate any code changes that you make in your Logstash pipeline.

## Acknowledgement

Thanks to my co-worker Joao Duarte at Elastic for coming up with the custom ruby filter that is presented in this blog.

## Code description

The code given below demonstrates an entire Logstash pipeline that creates a simulated input event that contains a message with multiple email addresses in it. It then processes the event with a custom ruby filter which finds and replaces each email addresses in the "message" field with its SHA1 digest, and then writes the modified event to stdout.

## Logstash pipeline

```
input {
    generator {
        lines => [
            '{"message": "Someone had an email address foobar@example.com and sent mail to foobaz@another-example.com"}'
        ]
        count => 1
        codec => "json"
    }
}

filter {
  ruby {
    init => "require 'digest'; @email_regex = /([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})/"
    code => "str = event.get('message'); event.set('message', str.gsub(@email_regex) {|v| Digest::SHA1.hexdigest(v) })"
  } 
}

output {
    stdout { codec => "rubydebug" }
}
```

## Executing the pipeline

The above pipeline can be executed with the following command line, which will automatically restart the pipeline each time it is modified:

```
./bin/logstash -f <your pipeline config file> --config.reload.automatic
```

This will generate the following output, which confirms that the email addresses in the message field (of the event created in the generator) have been replaced with the SHA1 hash value, as desired:

```
{
      "@version" => "1",
          "host" => "New2020MacBook.lan",
       "message" => "Someone had an email address 6f25d1a16b65ee184e83d06a268af7f44d4e8a10 and sent mail to f1377593215966404efb0f42c6ce48017c2c5522",
    "@timestamp" => 2022-01-20T17:50:10.598Z,
      "sequence" => 0
}
```

## Conclusion

In this brief post, I have demonstrated the following concepts:

1. How to use a generator to create a custom event to help easily verify the functionality of your Logstash filters and to help debug your Logstash pipeline.
2. How to define a custom Ruby filter in your Logstash pipeline.
3. How to make use of Ruby's gsub functionality along with a regular expression and a call to a SHA1.hexdigest function, for replacing sensitive text.
4. How to view the resulting modified events on stdout.
5. How to automatically reload your pipeline as your make edits.
