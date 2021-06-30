# Verification 

This module contains support code for the Crawler to enable identifying
HTML documents that are _actually_ privacy policies as opposed to
documents that represent pages referencing the privacy policy or
similar defects of the crawlers search process.

Most verification capability is imported from this module to the
crawler.py script.   By passing in a cosine similarity threshold, a directory path for the
ground truth you want to test against, an english dictionary, and your
test dataset directory, you can review the cosine similarity scores for
every HTML document as well as a more curated list of documents that
are on the borderline of the threshold you specified.


