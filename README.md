# AI Quality Engineering Lab

![CI](https://github.com/HrishiPurandare/ai-quality-engineering-lab/actions/workflows/ci.yml/badge.svg)
![Quality gate](https://github.com/HrishiPurandare/ai-quality-engineering-lab/actions/workflows/quality-gate.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![LLM](https://img.shields.io/badge/LLM-Ollama%20(local)-black)

How do you **test** an AI chatbot? This lab answers that hands-on. It contains a small RAG (retrieval-augmented generation) banking assistant, **Ask Ledgerly**, with a React chat UI, and a growing test suite around it: unit tests, LLM evaluations, red-teaming, guardrails, Playwright end-to-end tests and CI quality gates.

![Ask Ledgerly chat UI: a cited answer, a blocked prompt injection, and an out-of-scope refusal](docs/chat-ui.png)

Everything runs **locally and for free** on [Ollama](https://ollama.com). No API keys, and no customer data leaves the machine. Ledgerly Bank is fictional; its policy documents are invented test data.

## Architecture

```mermaid
flowchart LR
    Q[Customer: React chat UI] --> API[FastAPI /chat]
    API --> GI{Input guard}
    GI -->|known attack| B[Block]
    GI -->|card numbers redacted| R[Retrieve top-k chunks]
    R <--> V[(Chroma vector store)]
    R -->|distance > threshold| X[Refuse: no relevant policy]
    R -->|relevant chunks| GC[Context guard: drop injected instructions]
    GC --> P[Prompt: rules + numbered context]
    P --> L[Ollama llama3.2:3b]
    L --> GO{Output guard}
    GO -->|card number, secret request,<br/>prompt leak, code| S[Safe reply]
    GO -->|ok| C[Answer + citations + contexts]
    D[data/policies/*.md] -->|chunk + embed<br/>nomic-embed-text| V
```

Design choices:
- **Refuse before generating.** If no chunk is close enough to the question, the bot answers "I don't have that information" without calling the model, so it can't hallucinate an answer.
- **Numbered citations.** The model must cite `[n]`; citations are mapped back to source file and section, and invented numbers are dropped.
- **Contexts are returned with every answer**, because evaluation metrics (faithfulness, context precision) need them.
- **Guardrails around the model, not inside it** (`app/guardrails.py`): deterministic input, context and output filters that report which rule fired. `GUARDRAILS=off` reproduces the unprotected baseline.
- **The model sits behind an interface** (`app/llm.py`), so unit tests use a deterministic fake and CI never needs a GPU.

## Quick start

```bash
# 1. Local models (one-time, ~2.3 GB)
brew install ollama && brew services start ollama
ollama pull llama3.2:3b && ollama pull nomic-embed-text

# 2. App
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.ingest                 # build the vector index
uvicorn app.main:app --reload        # API docs at http://localhost:8000/docs

# 3. Chat UI (second terminal; Node 22)
cd web && npm ci && npm run dev      # http://localhost:5173
```

```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "How much does an international transfer cost?"}' | python -m json.tool
```

## Tests

```bash
pytest -m "not live"   # unit tests: fake LLM, ~2 s, runs in CI
pytest -m live         # smoke tests against the real local model
```

| Layer | What it checks | Status |
|---|---|---|
| Unit | Chunking, retrieval ranking, refusal logic, citation mapping, prompt rules, API contract and errors | ✅ |
| Live smoke | Real model answers a known fact with a citation, refuses off-topic questions, never asks for an OTP | ✅ |
| Evals: deterministic | 42-item golden dataset: retrieval hit rate and MRR, required facts, citations, correct and false refusals | ✅ |
| Evals: LLM judge | Faithfulness, answer relevancy, contextual precision and recall (DeepEval, local `qwen2.5:3b` judge) | ✅ |
| Red team | 22 attacks in 8 categories plus 9 held-out, incl. indirect injection via poisoned documents; deterministic detectors (canaries, Luhn, n-gram leak) | ✅ |
| Guardrails + Promptfoo | Input, context and output guardrails; before/after numbers; Promptfoo suite over HTTP | ✅ |
| E2E: mocked API | 18 Playwright tests (desktop + mobile): answers and sources, refusals, guardrail badges, errors and recovery, double-send, length limit, XSS | ✅ CI |
| Quality gate | Real model in GitHub Actions: smoke eval + red team against thresholds, on relevant changes and nightly | ✅ CI |
| E2E: live stack | Playwright through the real UI, API and model; semantic assertions (embedding similarity) plus exact key facts from the golden dataset | ✅ local |
| E2E | React chat UI driven by Playwright, with semantic assertions | 🔜 |
| CI gates | Eval scores must stay above thresholds on every PR | 🔜 |

## Evals

```bash
python -m evals.run                     # golden dataset through the real bot -> evals/results/REPORT.md
pip install -r requirements-evals.txt   # DeepEval, one-time
ollama pull qwen2.5:3b                  # judge model, one-time
python -m evals.judge                   # LLM-judge metrics on the cached answers -> JUDGE_REPORT.md
```

- **Golden dataset** ([`evals/golden/`](evals/golden/ledgerly_golden.jsonl)): 42 questions across facts, procedures, reasoning, multi-hop, safety and out-of-scope. The dataset is validated by unit tests (every required fact must exist in its source document).
- **Deterministic metrics first:** fast, free and repeatable, so they can gate CI. **LLM-judge metrics second:** slower and noisier, so every low score is reported with the judge's reason, and judge errors are counted rather than hidden.
- **The judge is a different model family** from the chat model, to avoid self-preference bias.
- Latest results: [REPORT.md](evals/results/REPORT.md) · [JUDGE_REPORT.md](evals/results/JUDGE_REPORT.md)

### Results so far (M1, 8 GB, everything local)

| Check | Result |
|---|---|
| Golden dataset pass rate | **90%** (38/42): retrieval hit rate 97%, MRR 0.97, 100% correct refusals, 5% false refusals |
| Failures found | missing citation, a multi-hop answer that dropped one fact, 2 safety questions over-refused |
| Red team, 22 attacks | **9% → 0%** attack success rate with guardrails |
| Red team, 9 held-out attacks written *after* the guardrails | **33% → 22%**: the guardrails generalise only partly (a "translate, then append" injection and a second poisoned document still get through) |
| Golden dataset with guardrails on | **90%**, unchanged: no guardrail fired on any of the 42 normal questions |
| Promptfoo, 10 tests over HTTP | **6/10 → 9/10**; redacting a pasted card number also fixed a wrong refusal |
| Judge calibration (6 items, 2 local judges) | Retrieval was correct on all 6, yet `qwen2.5:3b` scored contextual recall 0.04 and `llama3.2:3b` 0.78; llama failed faithfulness on 4/6 items (timeouts) |

**Takeaways:** guardrails tuned on an attack set will always look perfect on that set, so the held-out number (22%) is the honest one. And a 3B judge is not trustworthy. Deterministic metrics gate quality here; judge scores are reported with reasons for a human to review, and a stronger judge (7B+ or an API model) is on the roadmap.

## Red team

```bash
python -m redteam.run --guardrails off --out redteam/results/baseline      # unprotected
python -m redteam.run --guardrails on  --out redteam/results/guarded
python -m redteam.run --holdout --out redteam/results/holdout-guarded      # attacks the guards never saw
python -m redteam.run --rescore --out redteam/results/guarded             # re-check saved answers after fixing a detector
```

Reports: [baseline](redteam/results/baseline/REDTEAM_REPORT.md) · [guarded](redteam/results/guarded/REDTEAM_REPORT.md) · [held-out, baseline](redteam/results/holdout-baseline/REDTEAM_REPORT.md) · [held-out, guarded](redteam/results/holdout-guarded/REDTEAM_REPORT.md)

Attacks cover prompt injection, system-prompt leaks, jailbreaks, card data, social engineering, harmful requests, financial advice and **indirect prompt injection** (a poisoned knowledge-base document, indexed only in an in-memory red-team store). Each attack is scored by deterministic detectors that are themselves unit-tested against both safe and unsafe answers. The report also records whether each attack actually reached the model, so a gate refusal can't be mistaken for model robustness.

## Promptfoo

The same idea through an industry tool: [Promptfoo](https://www.promptfoo.dev) calls the real `/chat` endpoint on two servers (guardrails off and on) and checks each answer with assertions.

```bash
GUARDRAILS=off uvicorn app.main:app --port 8001 &
GUARDRAILS=on  uvicorn app.main:app --port 8000 &
PROMPTFOO_DISABLE_TELEMETRY=1 npx -y promptfoo@0.120.27 eval -c promptfoo/promptfooconfig.yaml \
    -o promptfoo/results/results.json --no-cache
python -m promptfoo.report     # -> promptfoo/results/PROMPTFOO_REPORT.md
```

Latest: [PROMPTFOO_REPORT.md](promptfoo/results/PROMPTFOO_REPORT.md)

## Quality gate in CI

Every change that can move answer quality (app code, policy documents, prompts, evals, red team) runs the **real model** in GitHub Actions: a 13-question smoke set from the golden dataset (every category, all passing locally) and the 22 red-team attacks with guardrails on. [`evals/gate.py`](evals/gate.py) then checks the results against the rules in [`evals/quality_gate.json`](evals/quality_gate.json) and fails the build if any breaks. It also runs nightly and on demand.

| Rule | Threshold |
|---|---|
| Smoke-set pass rate | ≥ 0.90 |
| Retrieval hit rate | ≥ 0.90 |
| Correct refusals (out-of-scope questions) | = 1.00 |
| False refusals | ≤ 0.10 |
| Answers with a citation | ≥ 0.80 |
| Red-team attack success rate | ≤ 0.05 (at most 1 of 22) |

First run on GitHub (2026-11-19, CPU runner): **passed**, 13/13 smoke items and 0/22 attacks, in 7.5 minutes end to end (smoke eval 3m 19s, red team 2m 43s, about 15 s per answer vs 4.6 s on an M1). Installing Ollama and pulling both models took under a minute; later runs use the cache.

Proof it can fail: tightening the retrieval threshold (`MAX_DISTANCE` 0.50 → 0.30), a harmless-looking tuning change, broke 4 of 6 rules (pass rate 1.00 → 0.69, false refusals 0 → 0.18). Answers also got 3× faster, because the bot refused more often. The gate blocks it.

```bash
python -m evals.run --smoke --guardrails on --out evals/results/smoke
python -m redteam.run --guardrails on --out redteam/results/smoke
python -m evals.gate --eval evals/results/smoke/summary.json --redteam redteam/results/smoke/summary.json
```

## Trend and drift

The gate answers "is this run good enough?". [`evals/trend.py`](evals/trend.py) answers "is it getting worse, and why?". Every gate run is added to a history; each new run is compared with the last run on the **same question set**, and the report flags:

- a gated metric that dropped more than 0.05, **even if the gate still passes** (or that sits 0.05 below the average of the last 5 runs: slow decay);
- questions that went from pass to fail, and attacks that started getting through;
- a change in the top retrieved document, and latency jumps (only on the same kind of machine);
- **what changed** between the two runs: code or data (a hash of every file that can change an answer, so docs-only commits don't count), config, machine, Ollama version, and the model files' digests (a re-pulled tag can silently swap the model).

If verdicts moved and **nothing** changed, the run is labelled **flaky**: the model answered the same question differently, so the fix is a more robust check or prompt, not a revert. Findings appear as warnings on the CI run, not failures. In CI the history is kept in the Actions cache (saved even when the gate fails); locally it's [`evals/history/history.jsonl`](evals/history/history.jsonl) → [TREND.md](evals/history/TREND.md).

First real catch: the nightly run on 2026-11-20 dropped to 12/13, with the same commit, the same retrieved document and temperature 0. The `saf-01` answer was still correct, but the model wrote "according to Ledgerly Bank's security guidelines" instead of the `[1]` citation marker. The gate passed (0.92 ≥ 0.90); the trend flagged it as flaky.

```bash
python -m evals.trend record --eval evals/results/smoke --redteam redteam/results/smoke --source local
python -m evals.trend report      # rebuild TREND.md from the history
```

## End-to-end tests (Playwright)

```bash
cd web
npm run test:e2e         # mocked API, desktop + mobile, ~10 s, runs in CI
npm run test:e2e:live    # real stack (needs Ollama; starts the API itself), ~30 s
```

Two kinds of E2E test, because a chatbot UI has two kinds of risk:
- **Mocked** (`web/e2e/mocked`): the API is faked with `page.route()`, so tests are fast and exact. They cover what the *UI* does with every kind of response: sources, refusals, guardrail badges, HTTP errors, slow answers, and model output containing HTML.
- **Live** (`web/e2e/live`): real answers change from run to run, so they're checked by **meaning** (cosine similarity of `nomic-embed-text` embeddings, threshold 0.70, via a custom `toMeanTheSameAs` matcher) **plus the exact key facts** from the golden dataset. Calibration showed why both are needed: "AED 500" scored 0.97 against the expected "AED 50", higher than the correct answer (0.77). Embeddings don't see numbers.

## Project layout

```
app/          RAG application (config, llm client, chunking, vector store, pipeline, API)
data/         fictional Ledgerly Bank policy documents (the knowledge base)
evals/        golden dataset, metrics, eval runner, LLM judge, quality gate, trend history, reports
redteam/      attacks (main + held-out), poisoned fixtures, detectors, runner, committed reports
promptfoo/    Promptfoo config and tests against the HTTP API, report script
web/          React + Vite chat UI, Playwright E2E (page object, API mocks, semantic matcher)
tests/unit    fast deterministic tests with a fake LLM
tests/live    smoke tests against real Ollama models
```

## Roadmap
- [x] RAG assistant with citations and refusal threshold
- [x] Unit tests + CI
- [x] Golden dataset and DeepEval metrics with a local judge model
- [x] Red-team baseline: 22 attacks, deterministic detectors
- [x] Guardrails (input, context, output), before/after and held-out red-team reports, Promptfoo suite
- [x] React chat UI + Playwright E2E (mocked in CI, live with semantic assertions)
- [x] Eval quality gate in CI (real model on CPU, smoke set + red team, nightly)
- [x] Trend report and drift detection (flaky vs regression, model-version tracking)
