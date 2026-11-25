# LLM-judge report: NovaAsk

Run on 2026-11-25 · judge `llama3.2:3b` (local, via Ollama) · answers from `llama3.2:3b` · 6 answered questions · threshold 0.7 · 9.1 min

| Metric | Mean | Pass rate | Judged | Judge errors | Question it asks |
|---|---|---|---|---|---|
| faithfulness | 0.667 | 60% | 5 | 1 | Is every claim in the answer supported by the retrieved context? (hallucination check) |
| answer_relevancy | 0.417 | 17% | 6 | 0 | Does the answer address the question, without padding? |
| contextual_precision | 0.986 | 100% | 6 | 0 | Are the chunks that matter ranked above the ones that don't? |
| contextual_recall | 0.857 | 75% | 4 | 2 | Does the retrieved context contain everything needed for the expected answer? |

## Lowest scores

Read the judge's reason before trusting a low score: a 3B judge is cheap but noisy.

| Item | Metric | Score | Judge's reason |
|---|---|---|---|
| fee-02 | faithfulness | 0.0 | The score is 0.00 because there are no contradictions in the actual output to justify a higher faithfulness score. |
| fee-05 | answer_relevancy | 0.0 | The score is 0.00 because there is no relevant information in the actual output to address the question about the cost of transferring money to another UAE bank in the mobile app. |
| fee-06 | answer_relevancy | 0.0 | The score is 0.00 because there are no irrelevant statements in the actual output, making it a perfect score. |
| fee-01 | answer_relevancy | 0.333 | The score is 0.33 because there are no irrelevant statements in the actual output, but the answer itself is not directly provided, indicating a need for further clarification or information to accurately determine the mo |
| fee-06 | faithfulness | 0.333 | The score is 0.33 because the actual output contains contradictions regarding international SWIFT transfer costs (AED 30 per transfer) and correspondent bank charges, indicating a lack of faithfulness to the retrieval co |
| fee-03 | contextual_recall | 0.429 | The score is 0.43 because the 1st sentence in the expected output cannot be attributed to any node in the retrieval context, as it does not mention the Everyday Current Account, which is not present in the retrieval cont |
| fee-04 | answer_relevancy | 0.5 | The score is 0.50 because there are no irrelevant statements in the actual output, but the answer itself is not directly addressed, as the question asks for the waiver of the monthly fee, implying a need for more specifi |
| fee-02 | answer_relevancy | 0.667 | The score is 0.67 because there are no irrelevant statements in the actual output, allowing the answer to focus on providing a relevant solution to the user's question about avoiding the Everyday Current Account maintena |
