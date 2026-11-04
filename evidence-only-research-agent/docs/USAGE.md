# Usage

Run commands from the project directory.

## Index

```bash
py -3 cli.py index ./examples/documents
py -3 cli.py index ./examples/documents --rebuild
py -3 cli.py index ./examples/documents --chunk-size 500 --chunk-overlap 80
```

The path may be a directory or one supported file. Directories are scanned recursively. Supported types are `.pdf`, `.txt`, `.md`, and `.markdown`. Other files are counted as skipped. Hidden files and directories are ignored.

The command prints how many documents were indexed, how many were reused, and which files failed or need OCR. Exit code 0 means at least one file was read without an extraction error. Exit code 1 means every supported file failed. Exit code 2 means the path was missing or contained no supported files.

Indexing again does not duplicate unchanged files. Delete a file and index again to drop it. `--rebuild` throws away the previous index first.

## Ask

```bash
py -3 cli.py ask "What limitations were reported?"
py -3 cli.py ask "What limitations were reported?" --format json
py -3 cli.py ask "What limitations were reported?" --show-passages --k 4 --threshold 0.2
```

Markdown is the default. JSON is a single object on stdout. With `--format json`, retrieved passages go to stderr so the stdout stream stays valid JSON.

Abstaining is a successful answer. The exit code is still 0. A missing index, a bad flag, or a provider failure exits 2 and prints `Error: ...` on stderr.

`--show-passages` is for inspection. The printed score is not evidence that the passage supports a claim.

## Inspect the index

```bash
py -3 cli.py sources
py -3 cli.py stats
py -3 cli.py show-source <chunk-id>
```

`sources` lists each file, its type, page count for PDFs, chunk count, OCR flag, and any warning. `show-source` prints one chunk's text and page range. The chunk id comes from a citation or from `--show-passages`.

## Evaluate

```bash
py -3 cli.py evaluate
py -3 cli.py evaluate --output examples/evaluation_results.json
```

Evaluation always rebuilds an index of `--documents` (default `examples/documents`) using the offline providers, then scores `--questions` (default `examples/questions.json`). Without `--index-dir`, that index is temporary and is deleted afterward. With `--index-dir`, that directory is rebuilt and replaced.

`--provider configured` uses `GENERATION_PROVIDER` from the environment. That can call the network and spend API credit. The default `extractive` provider does not.

## Web UI

```bash
py -3 -m streamlit run streamlit_app.py
```

The page calls `ResearchPipeline` for indexing and asking. It does not score answers on its own.

Index one of three inputs: the bundled `examples/documents` corpus, files you upload, or a folder or file path on this machine. Uploaded names are basenames. A path typed into the question box is not opened. The page keeps its index in a temporary session folder and does not write `data/index`.

The provider menu starts on `extractive`. Embeddings on the page are always `local`. `xai` uses `XAI_API_KEY` from the environment or `.env` and sends the question and the retrieved passages to xAI. `openai_compatible` sends the same payload to `OPENAI_COMPATIBLE_BASE_URL`. The server listens on `127.0.0.1`.

Markdown and JSON downloads are `render_markdown` and the verified response object. Passage scores stay on the Passages tab. A score is not evidence.
