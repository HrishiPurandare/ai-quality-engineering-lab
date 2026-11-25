# Eval report: NovaAsk

Run on 2026-11-25 · chat `llama3.2:3b` · embeddings `nomic-embed-text` · top_k 4 · max_distance 0.5 · Darwin arm64 · avg 2.73 s per answer · guardrails on

**Overall pass rate: 92%** (13 golden questions). An answerable item passes when it is not refused, states every required fact and cites the right policy file. An out-of-scope item passes when it is refused.

## Retrieval (answerable questions)

| Metric | Value | Meaning |
|---|---|---|
| Hit rate | 100% | an expected policy file was in the retrieved chunks |
| MRR | 1.0 | 1 = the right file was always ranked first |
| Source recall | 100% | share of expected files retrieved (matters for multi-hop) |

## Refusals

| Metric | Value | Meaning |
|---|---|---|
| Correct refusals | 100% | out-of-scope questions refused |
| Refused by the gate | 0% | of those, refused before calling the model |
| False refusals | 9% | answerable questions wrongly refused |

## Answers (answerable questions)

| Metric | Value |
|---|---|
| Required facts present | 83% |
| Has a citation | 91% |
| Cites an expected source | 91% |

## Pass rate by category

| Category | Pass rate |
|---|---|
| fact | 100% |
| multi_hop | 100% |
| out_of_scope | 100% |
| procedure | 0% |
| reasoning | 100% |
| safety | 100% |

## Failures

| Item | Why | Question | Answer |
|---|---|---|---|
| trf-02 | model refused | How high can I raise my daily transfer limit, and when does the new limit start? | Sorry, I can't share that. I can help with questions about NovaBank products and policies. Never share your card number, PIN, CVV or one-time password with any… |
