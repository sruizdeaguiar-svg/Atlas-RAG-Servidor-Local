# Atlas RAG Local 1.1.5

- Fixes llama.cpp discovery by comparing detected engine build numbers and selecting the newest build. On the test Mac, Atlas selected build 10815, which rejected Flint architecture, instead of installed build 11840. Explicitly configured engine paths are preserved.
- Unsupported llama architectures produce an actionable message naming the incompatible architecture.
- Fixes oMLX memory configuration: `--memory-guard` follows the Atlas option, using `off` when disabled and `safe` when enabled. Previously Atlas always imposed `safe`, causing HTTP 507 even when the user disabled the Atlas memory guard.
- Global macOS and Metal limits are unchanged. Real engine allocation errors still apply.
- Keeps the 65,536-token default context and expanded R variables/output from 1.1.4.

73 automated tests passed. These fixes run on the Mac server and also apply to the unchanged iPad 1.1.4 client.

Live tests using fictitious data: Flint UD-IQ3_XXS loaded in llama in 18.5 seconds and returned mean 22, sample size 3. Gemma 4 26B A4B QAT MLX 4bit loaded in oMLX in 13.4 seconds without HTTP 507 and returned the same correct values. Both used a configured context of 65,536. Engines were stopped after verification.
