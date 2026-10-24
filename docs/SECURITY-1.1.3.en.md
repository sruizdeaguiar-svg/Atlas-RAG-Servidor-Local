# Security review — 1.1.3

[Español](SEGURIDAD-1.1.3.md) · [Security policy](../SECURITY.md) · [README](../README.en.md)

Review date: 24 October 2026. This report describes confirmed problems and implemented mitigations. It does not assign CVEs or claim an independent penetration-test certification. Consult the release notes for final installation and device-verification status.

## Findings and fixes

| Finding | Impact and scope | Correction |
| --- | --- | --- |
| Request limit relied on Content-Length | A chunked request could exceed the intended limit before JSON validation, consuming memory. An isolated 43 MiB login request returned validation error 422 rather than rejection 413. No authentication bypass was established. | ASGI middleware counts actual received bytes before parsing: 256 KiB for normal mutations and 42 MiB for collection uploads, including chunked requests and incorrect declared lengths. |
| Document extraction lacked process isolation and sufficient expansion limits | Office ZIP expansion, huge tables or a parser failure could exhaust server resources. No working remote-code-execution exploit was established. | Extraction runs in a separate macOS sandbox with no network, read access limited to its input/runtime, and writes restricted to its temporary workspace. CPU, elapsed time, process-family RSS and output are bounded. Office archives and tables have explicit expansion, entry, sheet and cell limits. XML processing uses defusedxml. |
| Authentication resource use was insufficiently bounded | Many distinct failed usernames could grow the attempt cache; concurrent password hashing could exhaust CPU. | Bounded expiring attempt maps, per-user and per-IP rate limits, and at most two simultaneous password verifications. |
| Known advisories in installed external Python engines | The inspected oMLX and vLLM distributions included dependency versions listed in vulnerability feeds. Reachability varies by package and platform; an advisory is not proof of exploitation through Atlas. | Atlas-managed launches use isolated dependency overlays with certifi 2026.10.23, filelock 4.2.1, setuptools 84.1.0, opentelemetry-api 1.45.1 and Pillow 13.0.0. Original vendor installations are preserved. Launch fails if required overlays are missing. |
| Engines inherited a broad environment | Child engines could inherit unrelated credentials from the parent process environment. No disclosure was observed. | A restricted environment is constructed for managed engines rather than forwarding arbitrary environment variables. |

The external dependency overlays are reproduced by `scripts/prepare_engine_security.py` during application builds. They are bundled with the macOS runtime. Source archives include the preparation script, not the generated dependencies. These overrides require runtime compatibility testing when vendor engines are updated.

**The original oMLX/vLLM installations are not patched in place.** Starting those applications outside Atlas may use their original dependency versions. Update vendor applications independently. The Python scanner does not cover all native code in LM Studio, llama.cpp, R, Apple frameworks or the operating system.

## Functional corrections related to engine control

Provider/model controls share explicit activation and serialized operations. A stopped provider is no longer silently presented as already selected. LM Studio's restored API is stopped before the dedicated loopback listener starts; shutdown quits the application and helpers. Status inspection tolerates a process exiting during a query, and shutdown does not mistake zombies for running engines.

These are reliability fixes. They are not described as a confirmed privilege escalation or a data leak.

## Verification and limitations

- Regression tests cover actual-byte request limits, Office expansion limits, XML entity rejection, readable sandboxed CSV/XLSX/DOCX, existing authorization boundaries, OAuth, R isolation and engine ownership.
- A real HTTPS lifecycle test obtained embeddings and answers from llama.cpp, oMLX, vLLM and LM Studio with small installed models. All four dedicated ports were closed and no LM Studio processes remained afterwards.
- The locked Atlas dependencies in the earlier audit had no known findings. Patched oMLX and vLLM inventories also returned no known findings in the audit performed for this review. These results reflect the scanner/feed at audit time and do not prove absence of vulnerabilities.
- Static analysis produced dynamic-SQL warnings. Manual review found parameter placeholders for values and collection IDs; dynamically chosen update columns come from internal callers, not request field names. No exploitable SQL injection was confirmed in those locations.
- This review does not certify every model, native dependency, iOS release, external service or operating-system component. It does not replace vendor updates, backups or a separate security assessment.

Existing protections include server-side collection authorization, hashed session tokens, password hashing, origin/Host checks, private credential file permissions, consent for OpenAI context transfer, mandatory R sandboxing and iOS certificate fingerprint verification. No certificate validation, operating-system protection or account authentication is disabled by these fixes.
