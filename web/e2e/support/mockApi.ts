import type { Page, Route } from "@playwright/test";

export interface FakeAnswer {
  answer: string;
  citations?: { number: number; source: string; section: string }[];
  refused?: boolean;
  guardrails?: string[];
}

export const ANSWERS = {
  swift: {
    answer: "International transfers (SWIFT) cost AED 30 per transfer [1].",
    citations: [{ number: 1, source: "transfers-and-limits.md", section: "International transfers" }],
  },
  outOfScope: {
    answer: "I don't have that information. Please contact Ledgerly Bank on 800-LEDGER.",
    refused: true,
  },
  blocked: {
    answer:
      "I can only help with questions about Ledgerly Bank products and policies. " +
      "For anything else, please contact Ledgerly Bank on 800-LEDGER.",
    refused: true,
    guardrails: ["input:override_instructions"],
  },
  redacted: {
    answer: "A replacement card costs AED 35 [1].",
    citations: [{ number: 1, source: "cards.md", section: "Card fees" }],
    guardrails: ["input:redacted_card"],
  },
} satisfies Record<string, FakeAnswer>;

/** Fake GET /api/health. */
export async function mockHealth(page: Page, ok = true) {
  await page.route("**/api/health", (route) =>
    ok
      ? route.fulfill({ json: { status: "ok", indexed_chunks: 20 } })
      : route.fulfill({ status: 500, body: "down" }),
  );
}

/**
 * Fake POST /api/chat. `reply` decides the answer per question.
 * Returns the questions the UI actually sent, so tests can assert on the request too.
 */
export async function mockChat(
  page: Page,
  reply: (question: string) => FakeAnswer | { status: number },
  options: { delayMs?: number } = {},
): Promise<string[]> {
  const sent: string[] = [];
  await page.route("**/api/chat", async (route: Route) => {
    const { question } = route.request().postDataJSON() as { question: string };
    sent.push(question);
    if (options.delayMs) await new Promise((resolve) => setTimeout(resolve, options.delayMs));
    const result = reply(question);
    if ("status" in result) {
      await route.fulfill({ status: result.status, json: { detail: "error" } });
      return;
    }
    await route.fulfill({
      json: {
        question,
        answer: result.answer,
        citations: result.citations ?? [],
        contexts: [],
        refused: result.refused ?? false,
        guardrails: result.guardrails ?? [],
      },
    });
  });
  return sent;
}
