# LLM-judge report: NovaAsk

Run on 2026-11-25 · judge `qwen2.5:3b` (local, via Ollama) · answers from `llama3.2:3b` · 35 answered questions · threshold 0.7 · 40.9 min

| Metric | Mean | Pass rate | Judged | Judge errors | Question it asks |
|---|---|---|---|---|---|
| faithfulness | 0.578 | 52% | 33 | 2 | Is every claim in the answer supported by the retrieved context? (hallucination check) |
| answer_relevancy | 0.439 | 9% | 35 | 0 | Does the answer address the question, without padding? |
| contextual_precision | 0.1 | 6% | 35 | 0 | Are the chunks that matter ranked above the ones that don't? |
| contextual_recall | 0.024 | 0% | 31 | 4 | Does the retrieved context contain everything needed for the expected answer? |

## Lowest scores

Read the judge's reason before trusting a low score: a 3B judge is cheap but noisy.

| Item | Metric | Score | Judge's reason |
|---|---|---|---|
| fee-01 | contextual_precision | 0 | The provided retrieval contexts contain only information about fees and charges for different NovaBank accounts and card-related fees, and none about the monthly fee for the Everyday Current Account. This is why all node |
| fee-01 | contextual_recall | 0.0 | The score is 0.00 because none of the sentences in the original expected output are supported by the provided retrieval context. |
| fee-02 | answer_relevancy | 0.0 | The score is 0.00 because the irrelevant statements provide financial requirements rather than actionable advice on how to avoid the fee, making them not relevant to the question asked. |
| fee-02 | contextual_precision | 0 | The retrieval contexts contain multiple 'no' verdicts for nodes 1 through 4, indicating that none of the provided documents offer information on avoiding the maintenance fee for the Everyday Current Account. These nodes  |
| fee-02 | contextual_recall | 0.0 | The score is 0.00 because no part of the retrieval context directly addresses the requirement of keeping an average monthly balance of AED 5,000 or more, or having a salary of at least AED 8,000 credited to the account e |
| fee-03 | faithfulness | 0.0 | The score is 0.00 because there are no contradictions, indicating the `actual output` aligns perfectly with the `retrieval context`. |
| fee-03 | contextual_precision | 0 | The relevant node regarding the absence of a monthly maintenance fee is ranked first, while the other nodes, which discuss interest rates, minimum opening deposit, and ID updates, are ranked lower. These irrelevant nodes |
| fee-03 | contextual_recall | 0.0 | The score is 0.00 because the sentence 'No. The Smart Savings Account has no monthly maintenance fee.' does not directly correspond to any part of the provided retrieval context. |
| fee-04 | contextual_precision | 0 | The retrieval contexts contain no nodes that are relevant to the input question about the Premier Account's monthly fee. All nodes are ranked lower than the irrelevant nodes, hence the contextual precision score is 0.00. |
| fee-04 | contextual_recall | 0.0 | The score is 0.00 because None of the sentences in the retrieval context support the claim about the AED 150 monthly fee being waived for combined balances of AED 150,000 or more with NovaBank. |
| fee-05 | contextual_precision | 0 | The provided retrieval contexts are all ranked as 'no' because they do not contain any information about the cost of transferring to another UAE bank through the mobile app or online banking. They only cover fees and lim |
| fee-05 | contextual_recall | 0.0 | The score is 0.00 because none of the sentences in the expected output are supported by the provided retrieval context. |
| fee-06 | contextual_precision | 0 | The retrieval contexts contain multiple 'no' verdicts indicating that none of the documents mention the fee for an international SWIFT transfer. These 'no' verdicts are ranked first and are the only relevant information  |
| fee-07 | answer_relevancy | 0.0 | The statements provided are directly about the cost of a replacement card, which is relevant to the input question about the cost of a replacement debit card. However, they are repeated and do not offer a specific cost a |
| fee-07 | contextual_precision | 0 | The retrieval contexts contain no information about the cost of a replacement debit card, which is why all nodes are ranked as 'no'. If any of the documents had provided information about the cost, the nodes would have b |
