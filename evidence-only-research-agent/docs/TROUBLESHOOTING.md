# Troubleshooting

Messages below are the ones the CLI prints. Fix the cause, then rerun the command.

## No index at ...

`ask`, `sources`, `stats`, or `show-source` was pointed at a directory that has no manifest. Index first:

```bash
py -3 cli.py index ./documents --index-dir data/index
```

Use the same `--index-dir` for later commands, or set `INDEX_DIR`.

## No supported documents

The folder has no `.pdf`, `.txt`, `.md`, or `.markdown` files. Other extensions are skipped. Hidden files are ignored. Pass the directory that contains the documents, not an empty parent.

## The index is unreadable or incompatible

`manifest.json` or `embeddings.npy` is truncated, or it was written by a different index version. Rebuild:

```bash
py -3 cli.py index ./documents --rebuild
```

## Embedding settings do not match the index

`EMBEDDING_PROVIDER` or `EMBEDDING_DIMENSIONS` changed after indexing. Restore the old values or rebuild. Local and HTTP vectors are not interchangeable.

## CHUNK_OVERLAP must be smaller than CHUNK_SIZE

Overlap has to leave room for new tokens. The defaults are 120 and 800. Both count whitespace-separated words.

## XAI_API_KEY is not set

`GENERATION_PROVIDER=xai` was selected and the key is missing. Export the key, or set `GENERATION_PROVIDER=extractive` to stay offline.

## Model provider rejected the API key

The remote call returned HTTP 401 or 403. Replace the key. The error text should not echo the key.

## Could not reach the model provider

The base URL is wrong, the server is down, or the request timed out. Check `XAI_BASE_URL` or `OPENAI_COMPATIBLE_BASE_URL`, and raise `REQUEST_TIMEOUT_SECONDS` if the model is slow. This is a failure, not an abstention.

## The model did not return valid JSON

The remote response was not a JSON object. The client retries once with the parser error. If it still fails, the command exits. The extractive provider does not have this failure mode.

## OCR warning

A PDF page has an image or drawing and almost no text. Those pages are not searchable. OCR them with an external tool, replace the PDF, and index again. The warning is expected for `examples/documents/scans/empty_scan.pdf`.

## Unreadable or encrypted PDF

The file is corrupt or password-protected. The rest of the folder is still indexed. `stats` lists the file under extraction errors. Decrypt or repair it and index again.

## Empty retrieval or an abstention

The index has no sentence that overlaps the question enough. Try `--show-passages` to see what was retrieved. A low score is not a reason to lower the bar until an unrelated sentence is quoted. If the terms are absent, the unanswered reason is `missing_documents`.

A paraphrase can abstain under the extractive provider even when the idea is present in different words. That is the local provider's limit. A remote provider may word the claim differently, but the excerpt still has to be verbatim and the claim still has to overlap that excerpt.

## No chunk with that id

`show-source` only accepts chunk ids from the current index. Rebuilds and edits change ids when the text changes. Copy the id from a fresh citation or from `--show-passages`.

## pytest collected the wrong project

Run `py -3 -m pytest` inside `evidence-only-research-agent`, not in a parent directory.
