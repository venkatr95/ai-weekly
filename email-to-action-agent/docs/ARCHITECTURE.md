# Architecture

The design of the pipeline is in [../ARCHITECTURE.md](../ARCHITECTURE.md).

The recommended layout in the PRD uses the package name `email_agent` and one file per stage. This repository keeps those stages in `src/email_to_action/`:

| Stage | Module |
| --- | --- |
| Headers, threads, and `.eml` | `parser.py` |
| Quotes, signatures, disclaimers | `preprocessor.py` |
| Deadline phrases and calendar dates | `dates.py` |
| Tasks, owners, priority, dependencies, questions | `extractor.py` |
| Local provider boundary | `providers.py` |
| Draft reply | `reply.py` |
| Validation | `schemas.py` |
| Orchestration | `pipeline.py` |
| Markdown and public JSON | `report.py` |

`integrations/gmail.py` and `integrations/outlook.py` are not imported by the pipeline. They only fetch message text.
