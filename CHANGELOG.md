# Changelog

Dates are when the work landed. Versions follow [Semantic Versioning](https://semver.org).

## [1.0.0] - 2026-11-20

First complete version: a RAG banking assistant and the full quality toolkit around it.

### Assistant
- RAG over fictional Ledgerly Bank policies: FastAPI, Chroma, Ollama (`llama3.2:3b`, `nomic-embed-text`), numbered citations, refusal before generation when no policy is close enough.
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
