# Atlas RAG Local 1.1.4

- Managed engines default to **65,536 context tokens** across desktop and iPad selectors. The active context is displayed beside the model. Engine/model limits still apply.
- R output increased to **32 MiB per run**, removing the previous 200,000-character cut. R printing is expanded; reaching the limit marks the run incomplete. Results remain available in the UI, TXT and ZIP.
- R accepts up to **256 selected variables**, replacing the previous limit of 20 and matching the table reader limit.
- AI interpretation receives the complete saved R output, removing silent truncation at 20,000 characters.
- Context errors have a specific message. Engine response bodies that could echo private input are not exposed.
- Local inference timeout is 10 minutes to accommodate larger models.
- RAM estimates remain informational by default; blocking remains optional.

The permissions, document/R isolation and HTTPS validation from 1.1.3 remain in place. These changes do not broaden data access or enable cloud transmission.

Validation: 70 automated tests passed, including real R with 25 variables; 30 isolated HTTP/HTTPS checks passed. Tests use fictitious data.
