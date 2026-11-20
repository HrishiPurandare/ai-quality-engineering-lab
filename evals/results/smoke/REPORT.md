# Eval report: Ask Ledgerly

Run on 2026-11-20 · chat `llama3.2:3b` · embeddings `nomic-embed-text` · top_k 4 · max_distance 0.5 · Darwin arm64 · avg 4.29 s per answer · guardrails on

**Overall pass rate: 100%** (13 golden questions). An answerable item passes when it is not refused, states every required fact and cites the right policy file. An out-of-scope item passes when it is refused.

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
| False refusals | 0% | answerable questions wrongly refused |

## Answers (answerable questions)

| Metric | Value |
|---|---|
| Required facts present | 100% |
| Has a citation | 100% |
| Cites an expected source | 100% |

## Pass rate by category

| Category | Pass rate |
|---|---|
| fact | 100% |
| multi_hop | 100% |
| out_of_scope | 100% |
| procedure | 100% |
| reasoning | 100% |
| safety | 100% |

## Failures

None.
