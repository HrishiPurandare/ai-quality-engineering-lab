# LLM-judge report: Ask Ledgerly

Run on 2026-11-17 · judge `llama3.2:3b` (local, via Ollama) · answers from `llama3.2:3b` · 6 answered questions · threshold 0.7 · 12.6 min

| Metric | Mean | Pass rate | Judged | Judge errors | Question it asks |
|---|---|---|---|---|---|
| faithfulness | 1.0 | 100% | 2 | 4 | Is every claim in the answer supported by the retrieved context? (hallucination check) |
| answer_relevancy | 0.611 | 33% | 6 | 0 | Does the answer address the question, without padding? |
| contextual_precision | 0.986 | 100% | 6 | 0 | Are the chunks that matter ranked above the ones that don't? |
| contextual_recall | 0.783 | 67% | 6 | 0 | Does the retrieved context contain everything needed for the expected answer? |

## Lowest scores

Read the judge's reason before trusting a low score: a 3B judge is cheap but noisy.

| Item | Metric | Score | Judge's reason |
|---|---|---|---|
| fee-05 | answer_relevancy | 0.0 | The score is 0.00 because there is no relevant information in the actual output to address the question about the cost of transferring money to another UAE bank in the mobile app. |
| fee-02 | contextual_recall | 0.2 | The score is 0.20 because the sentence does not match any information in the retrieval context, specifically the lack of specific account details and conditions for waiving fees, resulting in a low contextual recall scor |
| fee-01 | answer_relevancy | 0.5 | The score is 0.50 because there are no irrelevant statements in the actual output, but the answer itself is not directly provided, indicating a need for further clarification or information to accurately determine the mo |
| fee-03 | contextual_recall | 0.5 | The score is 0.50 because the retrieval context lacks information about the Smart Savings Account's interest rates, opening process, and KYC requirements, resulting in a limited contextual recall. |
| fee-06 | answer_relevancy | 0.5 | The score is 0.50 because there are no irrelevant statements in the actual output, but the answer itself is not directly provided, indicating a need for further clarification or a more specific response to accurately ans |
| fee-02 | answer_relevancy | 0.667 | The score is 0.67 because the output is concise and directly addresses the question, but lacks specific details and examples to provide a more comprehensive answer, preventing it from being higher. |
