# Atlas user and administration guide

[Español](GUIA.md) · [README](../README.en.md) · [Project structure](STRUCTURE.en.md) · [iOS installation](../ios/INSTALL.en.md)

## Choose a data directory

Use Initial setup to choose a directory with enough free disk space. Atlas proposes external storage when available. The selected directory stores the database, document index, analyses, backups, trash and logs. AI model files remain in their engine's model directories. A small private credential store remains in the Mac user's account.

The disk indicator refers to the volume containing Atlas data. Available RAM is a separate system metric. Atlas process RSS includes descendants and may count shared pages; it is not exclusive physical memory. Changing the data directory opens a separate workspace rather than migrating the previous one. Keep the original directory until you have verified your backups.

## Add and index a collection

1. Open Collections and choose Add folder.
2. Use the folder browser. On Mac it can use the native picker; on iPad the browser lists folders on the Mac, not iPad storage.
3. Selecting a directory fills its path and proposes its folder name. A manually customized name is retained.
4. Choose the embedding engine and model. The built-in Apple option is local; compatible external engines expose their installed embedding models in a separate catalog.
5. Save and choose Index. Inspect progress and errors in Activity.

Only administrators may browse the Mac's folders. Internal data and credentials are excluded. Symlinks, hidden files and AppleDouble metadata are skipped. Supported formats include PDF with text or OCR, XLSX, CSV, TSV, DOCX and text; convert old binary XLS files to XLSX.

File size is limited to 40 MiB and PDF processing to 500 pages. Other parser limits may reject large or unusually structured documents; inspect the reported indexing error. Incremental indexing hashes files and replaces a document atomically. Unchanged indexed documents are retained. Cancellation preserves completed work. An unavailable collection drive produces an error while retaining its index.

Changing an embedding profile invalidates that collection's index and requires rebuilding it. Semantic search compares only matching model profiles and dimensions. If an external embedding endpoint changes behind the same model name, explicitly rebuild affected collections. OpenAI embeddings are disabled; indexing stays local.

## Search and ask your library

Select collections or leave the selection empty to search all authorized collections. Choose full-text, semantic or hybrid search. Semantic results depend on the embedding model and its language coverage; the built-in Apple language-specific profiles do not guarantee cross-language equivalence. Vector search scans collection vectors and targets moderate local libraries rather than millions of chunks.

Select an AI engine and model before asking a question. References open the indexed source preview or download. Reindex files changed since their last scan. Conversations belong to a user and become unavailable when source access is revoked. Treat generated answers as drafts and check their references.

## Manage local engines

Administrators can enable automatic management in Models & AI. Configure executable and model directories, then choose an engine and an installed model. Opening a page does not load a model. vLLM requires a model before its API can start. Explicit activation is also available for the current selection.

With automatic management, switching stops the previous managed engine before loading the next. A model change also releases the previous process. LM Studio shutdown unloads models, stops its API and quits its application. Managed APIs use loopback ports 18880–18883. External connections retain their own lifecycle unless an administrator explicitly confirms the separate external-engine stop action.

Context affects memory allocation when a managed model loads. Temperature, Top-P and output limits apply to individual requests. Atlas estimates memory before loading, including all MoE weights, context and buffers. A rejection means the model or settings exceed that estimate; reduce context or choose a smaller model rather than forcing a load.

Stop all Atlas engines releases managed processes without deleting weights. Stopping external detected engines is a separate confirmed operation and may interrupt other applications' requests.

## Connect OpenAI

Configure your own API credential, or use the OAuth flow offered for eligible accounts. Complete authorization on the Mac. Fetch the available model catalog and choose a supported reasoning level. Availability depends on your account and connection method. Atlas requests consent before sending the selected question or context. Never include credentials in documents, screenshots, support reports or the repository.

## Analyze data with R

1. Choose a CSV, TSV or XLSX dataset and, where applicable, its sheet.
2. Review columns, types, missing values and dataset size.
3. Describe the analysis for AI plan preparation, or choose a supported statistical method manually.
4. Review variables, assumptions and generated R code before execution.
5. Run the analysis, inspect results and plots, and optionally request AI interpretation.
6. Export a ZIP containing code, a CSV copy, source hash/schema, results, plots and `sessionInfo()`.

Supported methods include descriptive statistics, Pearson correlation, linear regression, two-group Welch tests, Wilcoxon, ANOVA and chi-square. AI produces a validated structured plan rather than arbitrary executable R. Atlas does not install packages requested by a model or document. Statistical suitability and interpretation require human review; correlation does not establish causation.

R operates on a copy, under a mandatory macOS sandbox without networking or access to unrelated user files. CPU, wall time, memory, output size and concurrency are bounded. A sandbox failure prevents execution.

## Users, files and backups

The first administrator creates users and assigns collection access. Readers and editors begin without collection permissions. Editors require explicit edit permission to index, edit files or run R. Readers can search and download only authorized documents. Disabling an account or changing its password invalidates sessions.

Text editing keeps a backup and checks conflicts. Trash retains files under the Atlas data directory with restoration metadata; restoration is manual in this version. Keep regular backups of the selected data directory and protect exported files separately. Downloaded analysis ZIPs and documents are no longer governed by server permissions.

## iPhone/iPad and troubleshooting

Enable local-network HTTPS on the Mac, pair using the current link or QR code, and sign in with an Atlas account. The mobile app verifies the certificate fingerprint and requests only local-network permission. Folder browsing and engine changes execute on the Mac and require the same server-side permissions as desktop actions.

If connection fails, check that Atlas is running, both devices share a reachable local network, and the URL shown in the Mac menu is current. Confirm local-network permission in iOS settings. Re-pair only after checking any changed certificate fingerprint on the Mac. Do not bypass certificate checks or expose the service through a public router port.

For an engine error, inspect its status and logs, confirm its executable and model directories, and check available memory. An installed model may still be incompatible with its engine. For indexing errors, inspect the file format, size and parser limits. Use fictitious documents and isolated state for development tests; do not run destructive integration scripts against your production library.
