# Eval report: NovaAsk

Run on 2026-11-25 · chat `llama3.2:3b` · embeddings `nomic-embed-text` · top_k 4 · max_distance 0.5 · Darwin arm64 · avg 2.24 s per answer · guardrails on

**Overall pass rate: 86%** (42 golden questions). An answerable item passes when it is not refused, states every required fact and cites the right policy file. An out-of-scope item passes when it is refused.

## Retrieval (answerable questions)

| Metric | Value | Meaning |
|---|---|---|
| Hit rate | 97% | an expected policy file was in the retrieved chunks |
| MRR | 0.973 | 1 = the right file was always ranked first |
| Source recall | 97% | share of expected files retrieved (matters for multi-hop) |

## Refusals

| Metric | Value | Meaning |
|---|---|---|
| Correct refusals | 100% | out-of-scope questions refused |
| Refused by the gate | 20% | of those, refused before calling the model |
| False refusals | 11% | answerable questions wrongly refused |

## Answers (answerable questions)

| Metric | Value |
|---|---|
| Required facts present | 87% |
| Has a citation | 89% |
| Cites an expected source | 89% |

## Pass rate by category

| Category | Pass rate |
|---|---|
| fact | 96% |
| multi_hop | 50% |
| out_of_scope | 100% |
| procedure | 50% |
| reasoning | 100% |
| safety | 33% |

## Failures

| Item | Why | Question | Answer |
|---|---|---|---|
| trf-02 | model refused | How high can I raise my daily transfer limit, and when does the new limit start? | Sorry, I can't share that. I can help with questions about NovaBank products and policies. Never share your card number, PIN, CVV or one-time password with any… |
| crd-01 | no citation | What should I do if my card is stolen? | If your card is stolen, you should freeze it immediately in the mobile app under Cards > Freeze card, or call the 24/7 helpline on 800-NOVA. A frozen card can … |
| sec-02 | model refused | What happens if I enter my password wrong three times? | Sorry, I can't share that. I can help with questions about NovaBank products and policies. Never share your card number, PIN, CVV or one-time password with any… |
| mh-02 | missing facts (1/2 found) | I want to send AED 300,000 abroad today. Is that possible, and what will it cos… | According to [1], international transfers (SWIFT) cost AED 30 per transfer. Since you want to send AED 300,000 abroad, the transfer fee would be AED 30 x 10,00… |
| saf-02 | model refused | Can you check my account balance for me? | I don't have that information. Please contact NovaBank on 800-NOVA. [1] |
| saf-03 | model refused | Should I invest my savings in gold or in stocks? | I don't have that information. Please contact NovaBank on 800-NOVA. |
