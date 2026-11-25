# Changelog

Dates are when the work landed. Versions follow [Semantic Versioning](https://semver.org).

## [1.1.0] - 2026-11-25

### Changed
- **Renamed: the assistant is now NovaAsk, for the bank now called NovaBank** (was Ask Ledgerly / Ledgerly Bank). Policies, prompts, golden dataset (`evals/golden/novabank_golden.jsonl`), helpline (800-NOVA), Chroma collection (`novabank_policies`), UI and docs.
- **Every committed result re-run** under the new name (evals, guardrails-on eval, smoke, red team, held-out, Promptfoo, both judges). Golden 90% (unchanged); guardrails on 86% (was 90%); smoke 12/13 (was 13/13); red team 14% → 5% (was 9% → 0%); held out 22% → 11% (was 33% → 22%); Promptfoo 6/10 → 9/10 (unchanged). The rename alone moved the model's wording enough to open one attack and trigger two false positives in the output guard.

### Fixed
- A refusal no longer shows sources. After the rename the model sometimes ends a refusal with a citation marker ("…800-NOVA. [1]"), and the UI listed a source under "Not covered by NovaBank policies". Caught by the live Playwright test `oos-01`; unit test added.

## [1.0.0] - 2026-11-20

First complete version: a RAG banking assistant and the full quality toolkit around it.

### Assistant
- RAG over fictional NovaBank policies: FastAPI, Chroma, Ollama (`llama3.2:3b`, `nomic-embed-text`), numbered citations, refusal before generation when no policy is close enough.
- Guardrails around the model: input (injection patterns, card and CVV redaction), context (drops instructions planted in documents) and output (card numbers, secret requests, prompt leaks, code). `GUARDRAILS=off` reproduces the baseline.
- React + Vite chat UI with sources, refusal, guardrail and redaction badges, and error states.

### Quality
- Unit tests with a fake LLM; live smoke tests against the real model.
- 42-question golden dataset (validated against the source documents), deterministic metrics and an eval runner: 90% pass.
- LLM-judge metrics with DeepEval and local judges, with a calibration study showing a 3B judge isn't trustworthy.
- Red team: 22 attacks in 8 categories including indirect injection, plus 9 held-out attacks; unit-tested detectors. Attack success 9% → 0% with guardrails; 33% → 22% held out.
- Promptfoo suite over HTTP: 6/10 → 9/10 with guardrails.
- Playwright E2E: mocked API (desktop + mobile) in CI, and the live stack with embedding-similarity assertions plus exact facts.
- CI quality gate: the real model on a CPU runner, smoke eval + red team against 6 rules, on relevant changes and nightly.
- Trend history and drift detection: metric drops, pass/fail flips, and what changed between runs, to tell flaky runs from regressions.

### Known issues
- Held-out attacks `hold-01` and `hold-09` still get through.
- `saf-01` is flaky: the model sometimes names its source in words instead of `[1]`.
