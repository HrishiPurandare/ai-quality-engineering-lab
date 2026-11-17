# LLM-judge report: Ask Ledgerly

Run on 2026-11-16 · judge `qwen2.5:3b` (local, via Ollama) · answers from `llama3.2:3b` · 35 answered questions · threshold 0.7 · 37.8 min

| Metric | Mean | Pass rate | Judged | Judge errors | Question it asks |
|---|---|---|---|---|---|
| faithfulness | 0.563 | 49% | 35 | 0 | Is every claim in the answer supported by the retrieved context? (hallucination check) |
| answer_relevancy | 0.417 | 11% | 35 | 0 | Does the answer address the question, without padding? |
| contextual_precision | 0.136 | 9% | 35 | 0 | Are the chunks that matter ranked above the ones that don't? |
| contextual_recall | 0.099 | 3% | 35 | 0 | Does the retrieved context contain everything needed for the expected answer? |

## Lowest scores

Read the judge's reason before trusting a low score: a 3B judge is cheap but noisy.

| Item | Metric | Score | Judge's reason |
|---|---|---|---|
| fee-01 | contextual_recall | 0.0 | The score is 0.00 because none of the sentences in the original expected output are supported by the provided retrieval context, indicating that the context does not contain relevant information to explain the content of |
| fee-02 | answer_relevancy | 0.0 | The score is 0.00 because all provided statements are irrelevant to avoiding the maintenance fee through account usage or behavior, focusing instead on financial requirements that are not directly related to the input qu |
| fee-02 | contextual_precision | 0 | The provided retrieval contexts contain no information relevant to avoiding the maintenance fee for the Everyday Current Account. They only list other fees and charges for different accounts and card types, which are ran |
| fee-02 | contextual_recall | 0.0 | The score is 0.00 because None of the sentences in the original expected output are supported by the node(s) in the retrieval context. |
| fee-03 | faithfulness | 0.0 | The score is 0.00 because there are no contradictions, indicating the `actual output` aligns perfectly with the `retrieval context`. |
| fee-03 | contextual_precision | 0 | The retrieval contexts contain multiple irrelevant nodes regarding interest rates, minimum opening deposit, and ID updates. These nodes are ranked lower than the relevant node discussing the absence of a monthly maintena |
| fee-04 | contextual_precision | 0 | The retrieval contexts contain multiple nodes that provide no information about the Premier Account's monthly fee or when it is waived. These nodes should be ranked higher than the nodes that do provide relevant informat |
| fee-04 | contextual_recall | 0.0 | The score is 0.00 because None of the provided sentences support the claim about the AED 150 monthly fee being waived for combined balances of AED 150,000 or more with Ledgerly Bank in the original expected output. |
| fee-05 | contextual_precision | 0 | The provided retrieval contexts contain no information about the cost of transferring to another UAE bank through the mobile app or online banking. They only cover fees and limits for transfers within Ledgerly Bank. The  |
| fee-05 | contextual_recall | 0.0 | The score is 0.00 because none of the sentences in the original expected output are supported by any of the nodes in the retrieval context. |
| fee-06 | contextual_precision | 0 | The provided retrieval contexts are all ranked as 'no' because they do not contain any information about the fee for an international SWIFT transfer. They only cover processing times for international SWIFT transfers, wh |
| fee-06 | contextual_recall | 0.0 | The score is 0.00 because none of the sentences in the original expected output are supported by the provided retrieval context. |
| fee-07 | answer_relevancy | 0.0 | The statements provided are directly about the cost of a replacement card, which is relevant to the input question about the cost of a replacement debit card. However, they are repeated and do not offer a specific cost a |
| fee-07 | contextual_precision | 0 | The retrieval contexts contain no nodes that mention the cost of a replacement debit card, which is relevant to the input. All nodes are about different aspects of debit cards (delivery, lost/stolen, and overdraft/late c |
| fee-07 | contextual_recall | 0.0 | The score is 0.00 because None of the sentences in the retrieval context support the claim that a replacement card is free when the card is replaced due to suspected fraud, as the retrieval context does not mention any s |
