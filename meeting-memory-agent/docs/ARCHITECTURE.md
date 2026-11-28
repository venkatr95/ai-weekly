# Architecture

See [../ARCHITECTURE.md](../ARCHITECTURE.md). That document is the module map, the index layout, and the question router.

Short version: parsers produce utterances, rules produce items, linking updates status across meetings, and answers quote those items or abstain. Citations are checked against stored segments. The corpus is `corpus.json` under the index directory. Nothing in the default path calls the network.
